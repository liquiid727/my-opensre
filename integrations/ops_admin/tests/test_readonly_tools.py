"""Exercise the closed provider against the task-scoped HTTP contract."""

from __future__ import annotations

import json
from dataclasses import replace
from http import HTTPStatus

import httpx
import pytest

from config.constants.ops_admin import OPS_ADMIN_MAX_RESPONSE_BYTES, OPS_ADMIN_QUERY_ENDPOINTS
from core.llm.types import ToolCall
from core.tool.execution import execute_tool_calls
from infrastructure.turn_host.runtime_policy import TaskBinding, bound_task_binding
from integrations.ops_admin.client import OpsAdminClient
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.tools.provider import OpsAdminToolProvider


def binding() -> TaskBinding:
    return TaskBinding.from_payload({
        "investigation_id": "17", "attempt_id": "23", "credential": "opaque-task-capability",
        "resource_id": "host:42", "start": "2026-10-30T00:00:00Z", "end": "2026-10-30T00:30:00Z",
    })


def test_real_provider_scope_and_transport_contract() -> None:
    calls: list[httpx.Request] = []
    trusted = binding()

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == f"Bearer {trusted.credential}"
        body = json.loads(request.content)
        assert body["attempt_id"] == "23"
        assert body["resource_id"] == "host:42"
        assert body["tool_call_id"] == request.headers["X-Request-ID"]
        return httpx.Response(HTTPStatus.OK, json={
            "evidence_id": "e17", "available": True,
            "data": {"access_token": trusted.credential, "message": f"capability={trusted.credential}"},
        })

    client = OpsAdminClient(OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond))
    provider = OpsAdminToolProvider(client)
    assert provider.action_tools(confirm_fn=None, is_tty=False) == []
    with bound_task_binding(trusted):
        tools = provider.action_tools(confirm_fn=None, is_tty=False)
        assert {tool.name for tool in tools} == set(OPS_ADMIN_QUERY_ENDPOINTS)
        for tool in tools:
            scope = trusted.scope()
            assert tool.validate_public_input(scope) is None
            assert tool.validate_public_input({**scope, "url": "http://other"})
            assert tool.validate_public_input({**scope, "resource_id": "host:99"})
            # Validation is repeated by execution even if schema validation is bypassed.
            assert tool(**{**scope, "resource_id": "host:99"})["error"] == "scope_rejected"
            executed = execute_tool_calls(
                [ToolCall(id="call-17", name=tool.name, input=scope)], [tool], {},
            )
            assert not executed[0].is_error
            result = executed[0].details
            assert isinstance(result, dict)
            assert result["evidence_id"] == "e17"
            assert trusted.credential not in json.dumps(result)
            assert not tool.requires_approval
            assert trusted.credential not in json.dumps(tool.public_input_schema)
    assert len(calls) == len(OPS_ADMIN_QUERY_ENDPOINTS)
    assert {str(call.url).rsplit("/", 1)[-1] for call in calls} == set(OPS_ADMIN_QUERY_ENDPOINTS.values())
    # A previously discovered tool is useless outside the turn or in another task.
    assert tools[0](**trusted.scope())["error"] == "scope_rejected"
    with bound_task_binding(replace(trusted, investigation_id="18")):
        assert tools[0](**trusted.scope())["error"] == "scope_rejected"
    assert len(calls) == len(OPS_ADMIN_QUERY_ENDPOINTS)


def test_multi_resource_provider_requires_one_authorized_resource_choice() -> None:
    trusted = TaskBinding.from_payload({
        "investigation_id": "17", "attempt_id": "23", "credential": "opaque-task-capability",
        "resource_id": "42", "start": "2026-10-30T00:00:00Z", "end": "2026-10-30T00:30:00Z",
        "resources": [
            {"type": "host", "id": "42", "environment": "test"},
            {"type": "k8s", "id": 7, "environment": "test", "namespace": "orders", "kind": "pod", "name": "api-1"},
        ],
    })
    calls: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(HTTPStatus.OK, json={"evidence_id": "multi", "available": True})

    client = OpsAdminClient(
        OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond)
    )
    with bound_task_binding(trusted):
        tools = OpsAdminToolProvider(client).action_tools(confirm_fn=None, is_tty=False)
        scope = {key: value for key, value in trusted.scope().items()}
        resource = trusted.resource_options()[1]
        selected = {**scope, "resource": resource}
        assert tools[0].validate_public_input(selected) is None
        assert tools[0](**selected)["evidence_id"] == "multi"
        assert tools[0](**{**scope, "resource": {"type": "host", "id": "999", "environment": "test"}})["error"] == "scope_rejected"
    assert calls[0]["resource_type"] == "k8s"
    assert calls[0]["resource_namespace"] == "orders"
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["denied", "redirect", "large", "invalid", "timeout"])
def test_untrusted_or_failed_backend_never_exposes_body(mode: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            raise httpx.ReadTimeout("secret provider error", request=request)
        if mode == "denied":
            return httpx.Response(HTTPStatus.FORBIDDEN, text="secret provider error")
        if mode == "redirect":
            return httpx.Response(HTTPStatus.TEMPORARY_REDIRECT, headers={"Location": "http://attacker"})
        if mode == "large":
            return httpx.Response(HTTPStatus.OK, content=b"x" * (OPS_ADMIN_MAX_RESPONSE_BYTES + 1))
        return httpx.Response(HTTPStatus.OK, text="secret provider error")

    client = OpsAdminClient(OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond))
    result = client.query(binding(), "ops_admin_query_logs")
    assert result["available"] is False
    assert result["error"]
    assert "secret provider error" not in json.dumps(result)


@pytest.mark.parametrize("url", ["", "file:///etc/passwd", "https://name:secret@example.com", "http://example.com/path", "http://example.com?token=x"])
def test_configuration_rejects_unsafe_origins(url: str) -> None:
    with pytest.raises(ValueError):
        OpsAdminConfig(url)


def test_governed_mcp_requires_review_profile_and_allowlist() -> None:
    from integrations.ops_admin.mcp_registry import parse_server

    server = parse_server({"name": "test", "transport": "sse", "endpoint": "https://mcp.test", "profile": "ops-admin-readonly", "allowedTools": ["status"], "enabled": True, "reviewed": False, "version": 1})
    assert not server.eligible(profile="ops-admin-readonly", tool="status")
    reviewed = parse_server({"name": "test", "transport": "sse", "endpoint": "https://mcp.test", "profile": "ops-admin-readonly", "allowedTools": ["status"], "enabled": True, "reviewed": True, "version": 2})
    assert reviewed.eligible(profile="ops-admin-readonly", tool="status")
    assert not reviewed.eligible(profile="other", tool="status")
    assert not reviewed.eligible(profile="ops-admin-readonly", tool="restart")


def test_mcp_registry_revoke_removes_active_server() -> None:
    from integrations.ops_admin.mcp_registry import MCPRegistry

    registry = MCPRegistry()
    registry.apply([{"name": "test", "transport": "sse", "endpoint": "https://mcp.test", "profile": "ops-admin-readonly", "allowedTools": ["status"], "enabled": True, "reviewed": True, "version": 1}], profile="ops-admin-readonly")
    assert registry.allowed("test", profile="ops-admin-readonly", tool="status")
    registry.revoke("test")
    assert not registry.allowed("test", profile="ops-admin-readonly", tool="status")


def test_reviewed_mcp_is_dynamic_and_revocable(monkeypatch) -> None:
    trusted = replace(binding(), user_id="7", profile_id="1", profile_version="2")
    state = {"enabled": True}
    calls: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/verify"):
            servers = [{"id": 9, "version": 3, "profile": "ops-admin-readonly", "environment": "test", "resourceType": "host", "resourceId": 42, "tools": [{"name": "status", "inputSchema": {"type": "object", "properties": {"service": {"type": "string"}}}}]}] if state["enabled"] else []
            return httpx.Response(200, json={"valid": True, "policy": {"profile_id": "1", "version": "2", "model_ref": "opensre-default", "instructions": "inspect", "native_tools": [], "mcp_servers": servers, "max_tool_calls": 3, "query_timeout_seconds": 10, "task_timeout_seconds": 120, "max_output_bytes": 4096, "can_propose_actions": False}})
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"available": True, "data": {"status": "ok"}})

    monkeypatch.setenv("OPS_ADMIN_OPENSRE_SERVICE_TOKEN", "service-token")
    client = OpsAdminClient(OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond))
    with bound_task_binding(trusted):
        tools = OpsAdminToolProvider(client).action_tools(confirm_fn=None, is_tty=False)
        mcp = next(tool for tool in tools if tool.name == "ops_admin_mcp_9_status")
        result = mcp(arguments={"service": "api"})
        assert result["status"] == "ok"
        assert calls[0]["serverId"] == 9
        assert calls[0]["input"]["version"] == 3
        assert trusted.credential not in json.dumps(result)
        state["enabled"] = False
        assert mcp(arguments={"service": "api"})["error"] == "mcp_revoked"


def test_dynamic_mcp_tool_maps_results_into_evidence_catalog(monkeypatch) -> None:
    trusted = replace(binding(), user_id="7", profile_id="1", profile_version="2")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/verify"):
            return httpx.Response(200, json={"valid": True, "policy": {"profile_id": "1", "version": "2", "model_ref": "opensre-default", "instructions": "inspect", "native_tools": [], "mcp_servers": [{"id": 9, "version": 3, "profile": "ops-admin-readonly", "environment": "test", "resourceType": "host", "resourceId": 42, "resourceNamespace": "", "resourceKind": "", "resourceName": "", "tools": [{"name": "status", "description": "status", "inputSchema": {"type": "object"}}]}], "max_tool_calls": 3, "query_timeout_seconds": 10, "task_timeout_seconds": 120, "max_output_bytes": 4096, "can_propose_actions": False}})
        return httpx.Response(200, json={"available": True, "status": "healthy"})

    monkeypatch.setenv("OPS_ADMIN_OPENSRE_SERVICE_TOKEN", "service-token")
    client = OpsAdminClient(OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond))
    with bound_task_binding(trusted):
        mcp = next(tool for tool in OpsAdminToolProvider(client).action_tools(confirm_fn=None, is_tty=False) if tool.name == "ops_admin_mcp_9_status")
        evidence: dict[str, object] = {}
        assert mcp.evidence_mapper is not None
        mcp.evidence_mapper(evidence, {"status": "healthy"}, {"arguments": {}})
        entries = evidence["catalog_entries"]
        assert isinstance(entries, list)
        assert entries[0]["source"] == "ops_admin_mcp:9:status"
        assert "healthy" in entries[0]["summary"]


def test_agent_proposal_tool_creates_pending_proposal(monkeypatch) -> None:
    from config.constants.ops_admin import OPS_ADMIN_PROPOSAL_TOOL

    trusted = replace(binding(), user_id="7", profile_id="1", profile_version="2")
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/verify"):
            return httpx.Response(200, json={"valid": True, "policy": {"profile_id": "1", "version": "2", "model_ref": "opensre-default", "instructions": "propose", "native_tools": [OPS_ADMIN_PROPOSAL_TOOL], "can_propose_actions": True, "environments": ["test"], "max_tool_calls": 3, "query_timeout_seconds": 10, "task_timeout_seconds": 120, "max_output_bytes": 4096}})
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 200, "data": {"id": 91, "status": "PENDING_APPROVAL", "version": 1}})

    monkeypatch.setenv("OPS_ADMIN_OPENSRE_SERVICE_TOKEN", "service-token")
    client = OpsAdminClient(OpsAdminConfig("http://ops-admin.test"), transport=httpx.MockTransport(respond))
    with bound_task_binding(trusted):
        tools = OpsAdminToolProvider(client).action_tools(confirm_fn=None, is_tty=False)
        proposal_tool = next(tool for tool in tools if tool.name == OPS_ADMIN_PROPOSAL_TOOL)
        result = proposal_tool(investigation_id="17", script_id=3, verify_script_id=4, variables={}, expected_result="healthy", verification="probe succeeds", rollback_instructions="restore prior state", expires_at="2030-01-01T00:00:00Z")
        assert result == {"id": 91, "status": "PENDING_APPROVAL", "version": 1}
        assert requests[0]["userId"] == 7
        assert requests[0]["input"]["action"] == "standard_job"
