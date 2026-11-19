"""Published application policy fetched through the task capability, never model input."""

from __future__ import annotations

from typing import Any

from config.constants.ops_admin import OPS_ADMIN_QUERY_ENDPOINTS, OPS_ADMIN_PROPOSAL_TOOL
from infrastructure.turn_host.runtime_policy import TaskBinding
from integrations.ops_admin.client import OpsAdminClient


def task_policy(client: OpsAdminClient, binding: TaskBinding) -> dict[str, Any] | None:
    """Fail closed for missing, stale or malformed published policy."""
    if not binding.profile_id:
        return None
    result = client.verify(binding)
    policy = result.get("policy")
    if result.get("valid") is not True or not isinstance(policy, dict):
        raise ValueError("profile_policy_unavailable")
    if (
        str(policy.get("profile_id")) != binding.profile_id
        or str(policy.get("version")) != binding.profile_version
        or policy.get("model_ref") != "opensre-default"
    ):
        raise ValueError("profile_policy_mismatch")
    tools = policy.get("native_tools")
    if not isinstance(tools, list) or any(name not in OPS_ADMIN_QUERY_ENDPOINTS and name != OPS_ADMIN_PROPOSAL_TOOL for name in tools):
        raise ValueError("profile_tools_invalid")
    if policy.get("can_propose_actions") is not True and OPS_ADMIN_PROPOSAL_TOOL in tools:
        raise ValueError("profile_proposal_invalid")
    for key, ceiling in (
        ("max_tool_calls", 1000),
        ("query_timeout_seconds", 60),
        ("task_timeout_seconds", 3600),
        ("max_output_bytes", 262144),
    ):
        value = policy.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= ceiling:
            raise ValueError("profile_limits_invalid")
    if not isinstance(policy.get("instructions"), str):
        raise ValueError("profile_instructions_invalid")
    mcp_servers = policy.get("mcp_servers", [])
    if not isinstance(mcp_servers, list) or len(mcp_servers) > 8:
        raise ValueError("profile_mcp_invalid")
    for server in mcp_servers:
        if not isinstance(server, dict) or type(server.get("id")) is not int or type(server.get("version")) is not int:
            raise ValueError("profile_mcp_invalid")
        if not isinstance(server.get("profile"), str) or not isinstance(server.get("environment"), str) or not isinstance(server.get("resourceType"), str) or type(server.get("resourceId")) is not int or server.get("resourceId") < 1:
            raise ValueError("profile_mcp_invalid")
        for field in ("resourceNamespace", "resourceKind", "resourceName"):
            if not isinstance(server.get(field, ""), str) or len(server.get(field, "")) > 512:
                raise ValueError("profile_mcp_invalid")
        tools = server.get("tools")
        if not isinstance(tools, list) or len(tools) > 256:
            raise ValueError("profile_mcp_invalid")
        for descriptor in tools:
            if not isinstance(descriptor, dict) or not isinstance(descriptor.get("name"), str) or not isinstance(descriptor.get("inputSchema"), dict):
                raise ValueError("profile_mcp_invalid")
    return policy
