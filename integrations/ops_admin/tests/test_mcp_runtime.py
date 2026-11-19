"""Governed MCP transport acceptance against a real local stdio server."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

from config.constants.ops_admin import OPS_ADMIN_MCP_SERVICE_TOKEN_ENV
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.mcp_runtime import GovernedMCPRuntime


def test_real_stdio_discovery_schema_scope_and_revocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery is unprivileged; every real call checks current schema and review."""
    server_path = tmp_path / "server.py"
    server_path.write_text('from mcp.server.mcpserver import MCPServer\napp = MCPServer("local-acceptance")\n@app.tool()\ndef read_status(resource: str) -> str:\n    return "healthy:" + resource\napp.run(transport="stdio")\n')
    monkeypatch.setenv(OPS_ADMIN_MCP_SERVICE_TOKEN_ENV, "local-only-token")
    server = {"version": 1, "transport": "stdio", "command": sys.executable,
              "args": [str(server_path)], "timeoutSeconds": 10, "enabled": False,
              "profile": "ops-admin-readonly", "environment": "test", "resourceType": "host", "resourceId": 1,
              "resourceNamespace": "", "resourceKind": "", "resourceName": ""}
    requests: list[bool] = []

    def control_plane(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer local-only-token"
        discovery = request.url.params["discover"] == "true"
        requests.append(discovery)
        return httpx.Response(200, json={"data": {"server": server}})

    runtime = GovernedMCPRuntime(OpsAdminConfig("http://127.0.0.1:1"), transport=httpx.MockTransport(control_plane))
    discovered = runtime.discover(1, 1)
    assert discovered["healthy"]
    tool = next(tool for tool in discovered["tools"] if tool["name"] == "read_status")
    kwargs = {"profile": "ops-admin-readonly", "environment": "test", "resource_type": "host", "resource_id": 1}
    with pytest.raises(ValueError, match="revoked"):
        runtime.call(1, 1, "read_status", {"resource": "host-1"}, **kwargs)
    server["enabled"] = True
    server["tools"] = {"read_status": tool["inputSchema"]}
    result = runtime.call(1, 1, "read_status", {"resource": "host-1"}, **kwargs)
    assert "healthy:host-1" in str(result)
    with pytest.raises(Exception, match="required property"):
        runtime.call(1, 1, "read_status", {}, **kwargs)
    with pytest.raises(ValueError, match="scope"):
        runtime.call(1, 1, "read_status", {"resource": "host-1"}, **{**kwargs, "resource_id": 2})
    with pytest.raises(ValueError, match="scope"):
        runtime.call(1, 1, "read_status", {"resource": "host-1"}, **{**kwargs, "resource_namespace": "wrong"})
    server["tools"] = {}
    with pytest.raises(ValueError, match="tool denied"):
        runtime.call(1, 1, "read_status", {"resource": "host-1"}, **kwargs)
    server["enabled"] = False
    with pytest.raises(ValueError, match="revoked"):
        runtime.call(1, 1, "read_status", {"resource": "host-1"}, **kwargs)
    assert requests == [True, False, False, False, False, False, False, False]
