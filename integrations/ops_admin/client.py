"""Bounded requests to fixed task-scoped Ops Admin endpoints."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

from config.constants.ops_admin import OPS_ADMIN_MAX_RESPONSE_BYTES, OPS_ADMIN_QUERY_ENDPOINTS
from config.constants.ops_admin import OPS_ADMIN_MCP_SERVICE_TOKEN_ENV
from config.llm_credentials import resolve_env_credential
from infrastructure.turn_host.runtime_policy import TaskBinding
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.results import sanitized_result


class OpsAdminClient:
    """One bounded request per call; redirects and ambient proxy credentials disabled."""

    def __init__(
        self, config: OpsAdminConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._config = config
        self._transport = transport

    def query(
        self,
        binding: TaskBinding,
        tool_name: str,
        *,
        resource: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Request a named read using only the validated trusted task scope."""
        endpoint = OPS_ADMIN_QUERY_ENDPOINTS.get(tool_name)
        if endpoint is None:
            return {"error": "tool_not_allowed", "available": False}
        return self._request(binding, endpoint, resource=resource, timeout_seconds=timeout_seconds)

    def verify(self, binding: TaskBinding) -> dict[str, Any]:
        """Recheck task liveness and current resource permission on the backend."""
        return self._request(binding, "verify")

    def call_mcp(
        self,
        binding: TaskBinding,
        *,
        server_id: int,
        version: int,
        tool: str,
        arguments: dict[str, Any],
        profile: str,
        environment: str,
        resource_type: str,
        resource_id: int,
        resource_namespace: str = "",
        resource_kind: str = "",
        resource_name: str = "",
    ) -> dict[str, Any]:
        """Call one reviewed MCP through the Ops Admin audit boundary."""
        if not binding.user_id:
            return {"error": "mcp_user_required", "available": False}
        token = resolve_env_credential(OPS_ADMIN_MCP_SERVICE_TOKEN_ENV)
        if not token:
            return {"error": "mcp_service_unavailable", "available": False}
        if not re.fullmatch(r"\d+", binding.investigation_id) or not re.fullmatch(r"\d+", binding.attempt_id):
            return {"error": "mcp_scope_invalid", "available": False}
        payload = {
            "userId": int(binding.user_id),
            "serverId": server_id,
            "input": {
                "version": version,
                "tool": tool,
                "arguments": arguments,
                "profile": profile,
                "environment": environment,
                "resourceType": resource_type,
                "resourceId": resource_id,
                "resourceNamespace": resource_namespace,
                "resourceKind": resource_kind,
                "resourceName": resource_name,
                "investigationId": int(binding.investigation_id),
                "attemptId": int(binding.attempt_id),
                "toolCallId": str(uuid4()),
                "start": binding.start,
                "end": binding.end,
            },
        }
        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self._config.base_url.rstrip('/')}/api/v1/internal/ai-mcp/call",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Service-ID": self._config.service_id,
                    },
                )
            if not response.is_success:
                return {"error": "mcp_call_rejected", "available": False}
            result = response.json()
            if isinstance(result, dict) and isinstance(result.get("data"), dict):
                result = result["data"]
            return result if isinstance(result, dict) else {"error": "invalid_response", "available": False}
        except (httpx.HTTPError, ValueError, TypeError, OverflowError):
            return {"error": "mcp_backend_unavailable", "available": False}

    def create_action_proposal(self, binding: TaskBinding, proposal: dict[str, Any]) -> dict[str, Any]:
        """Create a pending proposal through the authenticated service boundary."""
        if not binding.user_id:
            return {"error": "proposal_user_required", "available": False}
        token = resolve_env_credential(OPS_ADMIN_MCP_SERVICE_TOKEN_ENV)
        if not token:
            return {"error": "proposal_service_unavailable", "available": False}
        try:
            with httpx.Client(timeout=self._config.timeout_seconds, follow_redirects=False, trust_env=False, transport=self._transport) as client:
                response = client.post(f"{self._config.base_url.rstrip('/')}/api/v1/internal/ai-action-proposals", json={"userId": int(binding.user_id), "input": proposal}, headers={"Authorization": f"Bearer {token}", "X-Service-ID": self._config.service_id})
            if not response.is_success:
                return {"error": "proposal_rejected", "available": False}
            result = response.json()
            if isinstance(result, dict) and isinstance(result.get("data"), dict):
                result = result["data"]
            return result if isinstance(result, dict) else {"error": "invalid_response", "available": False}
        except (httpx.HTTPError, ValueError, TypeError, OverflowError):
            return {"error": "proposal_backend_unavailable", "available": False}

    def _request(
        self,
        binding: TaskBinding,
        endpoint: str,
        *,
        timeout_seconds: float | None = None,
        resource: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        call_id = str(uuid4())
        url = (
            f"{self._config.base_url.rstrip('/')}/api/v1/internal/ai-investigations/"
            f"{quote(binding.investigation_id, safe='')}/query/{endpoint}"
        )
        if endpoint == "verify":
            url = url.removesuffix("query/verify") + "verify"
        payload = {
            "attempt_id": binding.attempt_id,
            "tool_call_id": call_id,
            "resource_id": binding.resource_id,
            "start": binding.start,
            "end": binding.end,
        }
        if resource is not None:
            payload.update(
                resource_type=resource.get("type", ""),
                resource_id=resource.get("id", ""),
                resource_namespace=resource.get("namespace", ""),
                resource_kind=resource.get("kind", ""),
                resource_name=resource.get("name", ""),
            )
        try:
            with (
                httpx.Client(
                    timeout=timeout_seconds or self._config.timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {binding.credential}",
                        "X-Service-ID": self._config.service_id,
                        "X-Request-ID": call_id,
                    },
                ) as response,
            ):
                if not response.is_success:
                    return {"error": "query_rejected", "available": False}
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > OPS_ADMIN_MAX_RESPONSE_BYTES:
                        return {"error": "result_too_large", "available": False}
                    chunks.append(chunk)
                result = json.loads(b"".join(chunks))
            if not isinstance(result, dict):
                return {"error": "invalid_response", "available": False}
            cleaned = sanitized_result(result, binding.credential)
            return (
                cleaned
                if isinstance(cleaned, dict)
                else {"error": "invalid_response", "available": False}
            )
        except (httpx.HTTPError, ValueError, RecursionError):
            # Provider details and headers must never reach the model or response.
            return {"error": "backend_unavailable", "available": False}
