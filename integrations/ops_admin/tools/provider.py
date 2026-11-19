"""A complete closed tool set for investigation sessions."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from config.constants.ops_admin import OPS_ADMIN_PROPOSAL_TOOL, OPS_ADMIN_QUERY_ENDPOINTS
from core.agent_harness.agent_build_config import AgentBuildConfig
from core.agent_harness.ports import ConfirmFn, SessionState, ToolEventObserver
from core.agent_harness.tools import ActionToolScope
from core.agent_harness.tools.tool_context import ACTION_TOOL_CONTEXT_RESOURCE_KEY
from core.domain.types.evidence import record_evidence_entry, unique_evidence_source
from core.tool import EvidenceType, RegisteredTool, SideEffectLevel, ToolSurface
from infrastructure.turn_host.runtime_policy import current_task_binding
from integrations.ops_admin.client import OpsAdminClient
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.policy import task_policy
from tools.interactive_shell.actions.ask_choice import ask_user_choice_tool


class OpsAdminToolProvider:
    """No discovery expansion, shell fallback, or credentials in model-visible kwargs."""

    def __init__(
        self,
        client: OpsAdminClient,
        observer: ToolEventObserver | None = None,
        *,
        session: Any = None,
        console: Any = None,
    ) -> None:
        self._client = client
        self._observer = observer
        self._session = session
        self._console = console
        self._scope: ActionToolScope | None = None
        self._calls = 0
        self._started = time.monotonic()
        self._budget_lock = threading.Lock()

    def bind_session(self, session: Any) -> None:
        """Replace the pooled session reference before every turn."""
        self._session = session
        self._scope = None

    def bind_console(self, console: Any) -> None:
        """Replace the current turn's cancellation-aware console."""
        self._console = console
        self._calls = 0
        self._started = time.monotonic()

    def action_tools(
        self,
        *,
        confirm_fn: ConfirmFn | None,
        is_tty: bool | None,
        resolved_integrations: dict[str, Any] | None = None,
        turn_user_message: str = "",
    ) -> list[RegisteredTool]:
        """Rebuild schemas using the current task's non-secret immutable scope."""
        _ = resolved_integrations
        binding = current_task_binding()
        if binding is None:
            return []
        self._scope = ActionToolScope(
            session=self._session,
            console=self._console,
            confirm_fn=confirm_fn,
            is_tty=is_tty,
            turn_user_message=turn_user_message,
        )
        scope = {
            key: getattr(binding, key)
            for key in ("investigation_id", "attempt_id", "resource_id", "start", "end")
        }
        resource_options = binding.resource_options()
        multi_resource = bool(binding.resources)
        try:
            policy = task_policy(self._client, binding)
        except ValueError:
            return []
        allowed = policy["native_tools"] if policy else OPS_ADMIN_QUERY_ENDPOINTS
        tools = [self._proposal_tool(binding, scope, resource_options if multi_resource else ()) if name == OPS_ADMIN_PROPOSAL_TOOL else self._tool(name, scope, resource_options if multi_resource else ()) for name in allowed]
        if policy:
            tools.extend(self._mcp_tools(policy.get("mcp_servers", []), binding, scope))
        if self._session is not None:
            tools.append(ask_user_choice_tool)
        return tools

    def _mcp_tools(
        self, servers: list[dict[str, Any]], binding: Any, scope: dict[str, str]
    ) -> list[RegisteredTool]:
        """Expose only reviewed, task-scoped MCP schemas from the current policy."""
        options = [resource.as_payload() for resource in binding.resources]
        tools: list[RegisteredTool] = []
        for server in servers:
            resource = {"type": server.get("resourceType", ""), "id": str(server.get("resourceId", "")), "environment": server.get("environment", ""), "namespace": server.get("resourceNamespace", ""), "kind": server.get("resourceKind", ""), "name": server.get("resourceName", "")}
            if options and not any(all(resource.get(key, "") == option.get(key, "") for key in ("type", "id", "environment", "namespace", "kind", "name")) for option in options):
                continue
            for descriptor in server.get("tools", []):
                name = descriptor["name"]
                safe_name = f"ops_admin_mcp_{server['id']}_{name}"
                tools.append(self._mcp_tool(safe_name, server, descriptor, resource, scope))
        return tools

    def _mcp_tool(
        self,
        name: str,
        server: dict[str, Any],
        descriptor: dict[str, Any],
        resource: dict[str, str],
        scope: dict[str, str],
    ) -> RegisteredTool:
        mcp_name = descriptor["name"]
        # A reviewed write tool is exposed as a request-only call: Ops Admin never
        # executes it here, it only creates a pending approval. The registered
        # side effect stays READ_ONLY because this call cannot change the target;
        # the mutation happens server-side after a different human approves it.
        write_tool = descriptor.get("sideEffect") == "write"

        def run(**kwargs: Any) -> dict[str, Any]:
            binding = current_task_binding()
            if binding is None or any(getattr(binding, key) != value for key, value in scope.items()):
                return {"error": "scope_rejected", "available": False}
            arguments = kwargs.get("arguments")
            if set(kwargs) != {"arguments"} or not isinstance(arguments, dict):
                return {"error": "mcp_arguments_rejected", "available": False}
            try:
                policy = task_policy(self._client, binding)
            except ValueError:
                return {"error": "mcp_revoked", "available": False}
            if not policy or not any(
                server.get("id") == item.get("id") and server.get("version") == item.get("version")
                for item in policy.get("mcp_servers", [])
            ):
                return {"error": "mcp_revoked", "available": False}
            with self._budget_lock:
                if self._calls >= policy["max_tool_calls"] or time.monotonic() - self._started >= policy["task_timeout_seconds"]:
                    return {"error": "profile_limit_or_revocation", "available": False}
                self._calls += 1
            return self._client.call_mcp(
                binding,
                server_id=server["id"],
                version=server["version"],
                tool=mcp_name,
                arguments=arguments,
                profile=server["profile"],
                environment=resource["environment"],
                resource_type=resource["type"],
                resource_id=int(resource["id"]),
                resource_namespace=resource["namespace"],
                resource_kind=resource["kind"],
                resource_name=resource["name"],
            )

        def map_evidence(evidence: dict[str, Any], output: dict[str, Any], _tool_input: dict[str, Any]) -> None:
            summary = json.dumps(output, ensure_ascii=False, separators=(",", ":"))[:2000]
            source = unique_evidence_source(evidence, f"ops_admin_mcp:{server['id']}:{mcp_name}")
            record_evidence_entry(
                evidence,
                source=source,
                label=f"MCP {mcp_name} on {resource['type']}:{resource['id']}",
                summary=summary,
            )

        base_description = descriptor.get("description") or "审核后的只读 MCP 工具；结果必须作为外部证据核对。"
        if write_tool:
            base_description = (
                "写操作（需人工审批）：调用只会提交审批，不会执行；批准后由服务端执行。"
                "不要重复提交同一调用，结果以调查时间线为准。 " + base_description
            )
        return RegisteredTool(
            name=name,
            description=base_description,
            input_schema={
                "type": "object",
                "properties": {"arguments": descriptor["inputSchema"]},
                "required": ["arguments"],
                "additionalProperties": False,
            },
            source="ops_admin",
            run=run,
            evidence_type=EvidenceType.OTHER,
            evidence_mapper=map_evidence,
            side_effect_level=SideEffectLevel.READ_ONLY,
            surfaces=(ToolSurface.CHAT, ToolSurface.ACTION),
            requires=["ops_admin", "mcp"],
        )

    def _proposal_tool(self, binding: Any, scope: dict[str, str], resource_options: tuple[dict[str, str], ...]) -> RegisteredTool:
        def run(**kwargs: Any) -> dict[str, Any]:
            current = current_task_binding()
            if current is None or any(getattr(current, key) != value for key, value in scope.items()):
                return {"error": "scope_rejected", "available": False}
            try:
                policy = task_policy(self._client, current)
            except ValueError:
                return {"error": "proposal_revoked", "available": False}
            if not policy or not policy.get("can_propose_actions") or OPS_ADMIN_PROPOSAL_TOOL not in policy.get("native_tools", []):
                return {"error": "proposal_not_allowed", "available": False}
            selected = kwargs.get("resource")
            if resource_options and selected not in resource_options:
                return {"error": "scope_rejected", "available": False}
            fallback_id = current.resource_id.rsplit(":", 1)[-1]
            resource = selected or (resource_options[0] if resource_options else {"type": "host", "id": fallback_id, "environment": (policy.get("environments") or [""])[0]})
            try:
                proposal = {
                    "investigationId": int(kwargs["investigation_id"]),
                    "environment": resource.get("environment", ""),
                    "resourceType": resource.get("type", ""),
                    "resourceId": int(resource.get("id", "0")),
                    "action": "standard_job",
                    "parameters": {"scriptId": int(kwargs["script_id"]), "verifyScriptId": int(kwargs["verify_script_id"]), "variables": kwargs["variables"]},
                    "risk": "low",
                    "expectedResult": kwargs["expected_result"],
                    "verification": kwargs["verification"],
                    "rollbackInstructions": kwargs["rollback_instructions"],
                    "expiresAt": kwargs["expires_at"],
                }
            except (KeyError, TypeError, ValueError):
                return {"error": "proposal_arguments_rejected", "available": False}
            if not isinstance(proposal["parameters"]["variables"], dict):
                return {"error": "proposal_arguments_rejected", "available": False}
            return self._client.create_action_proposal(current, proposal)

        properties: dict[str, Any] = {
            "investigation_id": {"type": "string", "enum": [scope["investigation_id"]]},
            "script_id": {"type": "integer", "minimum": 1},
            "verify_script_id": {"type": "integer", "minimum": 1},
            "variables": {"type": "object", "additionalProperties": {"type": "string"}},
            "expected_result": {"type": "string", "minLength": 1, "maxLength": 2000},
            "verification": {"type": "string", "minLength": 1, "maxLength": 2000},
            "rollback_instructions": {"type": "string", "minLength": 1, "maxLength": 2000},
            "expires_at": {"type": "string", "format": "date-time"},
        }
        required = ["investigation_id", "script_id", "verify_script_id", "variables", "expected_result", "verification", "rollback_instructions", "expires_at"]
        if resource_options:
            properties["resource"] = {"type": "object", "enum": list(resource_options), "additionalProperties": False}
            required.append("resource")
        return RegisteredTool(name=OPS_ADMIN_PROPOSAL_TOOL, description="创建待人工审批的低风险标准作业提案；不会自动批准或执行。", input_schema={"type": "object", "properties": properties, "required": required, "additionalProperties": False}, source="ops_admin", run=run, side_effect_level=SideEffectLevel.READ_ONLY, surfaces=(ToolSurface.CHAT, ToolSurface.ACTION), requires=["ops_admin", "governance"])

    def _tool(
        self,
        name: str,
        scope: dict[str, str],
        resource_options: tuple[dict[str, str], ...] = (),
    ) -> RegisteredTool:
        def run(**kwargs: Any) -> dict[str, Any]:
            binding = current_task_binding()
            selected_resource = None
            expected = scope
            if resource_options:
                selected_resource = kwargs.get("resource")
                expected = {**scope, "resource": selected_resource}
            if binding is None or kwargs != expected or (
                resource_options and selected_resource not in resource_options
            ):
                return {"error": "scope_rejected", "available": False}
            if any(getattr(binding, key) != value for key, value in scope.items()):
                return {"error": "scope_rejected", "available": False}
            try:
                policy = task_policy(self._client, binding)
            except ValueError:
                return {"error": "profile_rejected", "available": False}
            if policy:
                with self._budget_lock:
                    if (
                        name not in policy["native_tools"]
                        or self._calls >= policy["max_tool_calls"]
                        or time.monotonic() - self._started >= policy["task_timeout_seconds"]
                    ):
                        return {"error": "profile_limit_or_revocation", "available": False}
                    self._calls += 1
            result = self._client.query(
                binding,
                name,
                resource=selected_resource,
                timeout_seconds=policy["query_timeout_seconds"] if policy else None,
            )
            if (
                policy
                and len(json.dumps(result, ensure_ascii=False).encode())
                > policy["max_output_bytes"]
            ):
                return {"error": "profile_output_limit", "available": False}
            return result

        properties = {
            key: {"type": "string", "enum": [value]} for key, value in scope.items()
        }
        if resource_options:
            properties["resource"] = {
                "type": "object",
                "enum": list(resource_options),
                "additionalProperties": False,
            }
        required = [*scope, "resource"] if resource_options else list(scope)
        return RegisteredTool(
            name=name,
            description="Read scoped Ops Admin evidence. Missing/unavailable data is not healthy. Use the exact task scope shown in parameter enums.",
            input_schema={
                "type": "object",
                "properties": {
                    **properties,
                },
                "required": required,
                "additionalProperties": False,
            },
            source="ops_admin",
            run=run,
            side_effect_level=SideEffectLevel.READ_ONLY,
            surfaces=(ToolSurface.CHAT, ToolSurface.ACTION),
            requires=["ops_admin"],
        )

    def tool_resources(self) -> dict[str, Any]:
        """No runtime resources can expand the tool catalog."""
        return {ACTION_TOOL_CONTEXT_RESOURCE_KEY: self._scope} if self._scope else {}

    def observer(self, *, message: str) -> ToolEventObserver:
        """Forward only the host's existing observer."""
        _ = message
        return self._observer or (lambda _kind, _data: None)


def readonly_build_config(config: OpsAdminConfig) -> AgentBuildConfig:
    """Inject the closed provider via the standard harness construction seam."""

    def build_tools(
        session: SessionState,
        console: Any,
        logger: logging.Logger,
        observer: ToolEventObserver | None,
    ) -> OpsAdminToolProvider:
        _ = logger
        return OpsAdminToolProvider(
            OpsAdminClient(config), observer, session=session, console=console
        )

    return AgentBuildConfig(build_tools=build_tools)
