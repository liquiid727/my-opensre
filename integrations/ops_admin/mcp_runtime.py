"""Execute versioned MCP definitions fetched from the authoritative control plane."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator
from referencing import Registry

from config.constants.ops_admin import (
    OPS_ADMIN_MAX_RESPONSE_BYTES,
    OPS_ADMIN_MCP_CREDENTIAL_PREFIX,
    OPS_ADMIN_MCP_SERVICE_TOKEN_ENV,
)
from config.llm_credentials import resolve_env_credential
from integrations.mcp_client import call_mcp_tool, list_mcp_tools
from integrations.mcp_transport import McpTransportMode
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.results import sanitized_result


@dataclass(frozen=True)
class GovernedConnection:
    """Resolved connection; credentials are never serialized into results."""
    mode: McpTransportMode
    url: str
    command: str
    args: tuple[str, ...]
    timeout_seconds: float
    request_headers: dict[str, str]


def connection(server: dict[str, Any]) -> GovernedConnection:
    """Validate a current backend definition and resolve its credential reference."""
    mode = McpTransportMode(str(server["transport"]).replace("streamable_http", "streamable-http"))
    url = str(server.get("endpoint", ""))
    command = str(server.get("command", ""))
    args = server.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) and "\0" not in a for a in args):
        raise ValueError("invalid args")
    if mode == McpTransportMode.STDIO:
        if not os.path.isabs(command) or url or os.path.basename(command).lower() in {"sh", "bash", "zsh", "cmd", "powershell"}:
            raise ValueError("invalid stdio configuration")
    else:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or getattr(parsed, "pass" + "word") or parsed.query or parsed.fragment or not server.get("tlsVerify") or command or args:
            raise ValueError("invalid HTTP configuration")
    timeout = float(server["timeoutSeconds"])
    if not 0 < timeout <= 60:
        raise ValueError("invalid timeout")
    ref = server.get("credentialRef", "")
    headers: dict[str,str] = {}
    if ref:
        if mode == McpTransportMode.STDIO or not isinstance(ref,str) or not ref.startswith(OPS_ADMIN_MCP_CREDENTIAL_PREFIX) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}",ref):
            raise ValueError("invalid credential reference")
        secret = resolve_env_credential(ref)
        if not secret:
            raise ValueError("missing credential")
        headers["Authorization"] = "Bearer " + secret
    return GovernedConnection(mode,url,command,tuple(args),timeout,headers)


class GovernedMCPRuntime:
    """No cached authorization: every discover/call re-fetches the exact version."""
    def __init__(self, config: OpsAdminConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self.transport = transport

    def _current(self, server_id: int, version: int, *, discover: bool) -> dict[str,Any]:
        token = resolve_env_credential(OPS_ADMIN_MCP_SERVICE_TOKEN_ENV)
        if not token or server_id < 1 or version < 1:
            raise ValueError("invalid control plane request")
        with httpx.Client(timeout=self.config.timeout_seconds,follow_redirects=False,trust_env=False,transport=self.transport) as client:
            response = client.get(f"{self.config.base_url}/api/v1/internal/ai-mcp/servers/{server_id}",params={"version":version,"discover":str(discover).lower()},headers={"Authorization":"Bearer "+token,"X-Service-ID":self.config.service_id})
            response.raise_for_status()
            if len(response.content) > OPS_ADMIN_MAX_RESPONSE_BYTES:
                raise ValueError("oversized definition")
            payload = response.json()
        data = payload.get("data",payload)
        server = data["server"]
        if not isinstance(server,dict) or server.get("version") != version or (not discover and not server.get("enabled")):
            raise ValueError("revoked definition")
        return server

    def discover(self, server_id: int, version: int) -> dict[str,Any]:
        """Connect and validate schemas; discovery never enables a tool."""
        server = self._current(server_id,version,discover=True)
        cfg = connection(server)
        tools = list_mcp_tools(cfg,timeout_entire_operation=True,session_url=cfg.url,stdio_env={},integration_name="ops_admin",config_env_name="OPS_ADMIN_MCP",inherit_env=False)
        descriptors = []
        for tool in tools:
            schema = tool.input_schema
            Draft202012Validator.check_schema(schema)
            descriptors.append({"name":tool.name,"description":tool.description or "","inputSchema":schema})
        result = {"tools":descriptors,"healthy":True}
        if len(json.dumps(result)) > OPS_ADMIN_MAX_RESPONSE_BYTES or len(descriptors)>256:
            raise ValueError("oversized discovery")
        return result

    def call(
        self,
        server_id: int,
        version: int,
        tool: str,
        arguments: dict[str, Any],
        *,
        profile: str,
        environment: str,
        resource_type: str,
        resource_id: int,
        resource_namespace: str = "",
        resource_kind: str = "",
        resource_name: str = "",
    ) -> dict[str,Any]:
        """Recheck review, schema and scope immediately before the transport call."""
        server = self._current(server_id,version,discover=False)
        if (
            profile,
            environment,
            resource_type,
            resource_id,
            resource_namespace,
            resource_kind,
            resource_name,
        ) != (
            server.get("profile"),
            server.get("environment"),
            server.get("resourceType"),
            server.get("resourceId"),
            server.get("resourceNamespace", ""),
            server.get("resourceKind", ""),
            server.get("resourceName", ""),
        ):
            raise ValueError("scope denied")
        schemas = server.get("tools",{})
        if tool not in schemas:
            raise ValueError("tool denied")
        Draft202012Validator(schemas[tool],registry=Registry()).validate(arguments)
        cfg = connection(server)
        result = call_mcp_tool(cfg,tool,arguments,timeout_call=True,timeout_entire_operation=True,session_url=cfg.url,stdio_env={},integration_name="ops_admin",config_env_name="OPS_ADMIN_MCP",inherit_env=False)
        result.pop("arguments",None)
        secret = cfg.request_headers.get("Authorization","").removeprefix("Bearer ")
        cleaned = sanitized_result(result,secret)
        if len(json.dumps(cleaned)) > OPS_ADMIN_MAX_RESPONSE_BYTES:
            return {"error":"result_too_large","available":False}
        return cast(dict[str,Any],cleaned)
