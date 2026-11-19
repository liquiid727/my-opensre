"""Governed MCP registry bindings supplied by Ops Admin.

This module deliberately does not connect on discovery. A connection is only
eligible when the server is enabled, reviewed, bound to this profile, and the
requested tool is allowlisted.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class GovernedMCPServer:
    """A non-secret MCP definition returned by the control plane."""

    name: str
    transport: str
    endpoint: str
    profile: str
    allowed_tools: frozenset[str]
    enabled: bool
    reviewed: bool
    version: int

    def eligible(self, *, profile: str, tool: str) -> bool:
        """Return whether this exact version may call ``tool``."""
        return (
            self.enabled
            and self.reviewed
            and self.profile == profile
            and tool in self.allowed_tools
        )


def parse_server(payload: dict[str, object]) -> GovernedMCPServer:
    """Validate a control-plane record without accepting credentials."""
    required = {"name", "transport", "profile", "enabled", "reviewed", "version"}
    if not required.issubset(payload) or "allowedTools" not in payload and "tools" not in payload:
        raise ValueError("invalid MCP registry record")
    name = payload["name"]
    transport = payload["transport"]
    endpoint = payload.get("endpoint", "")
    profile = payload["profile"]
    if not all(isinstance(value, str) and value.strip() for value in (name, transport, profile)):
        raise ValueError("invalid MCP registry identity")
    transport = "streamable_http" if transport == "streamable-http" else transport
    if transport not in {"stdio", "sse", "streamable_http"}:
        raise ValueError("unsupported MCP transport")
    if not isinstance(endpoint, str):
        raise ValueError("invalid MCP endpoint")
    if transport != "stdio":
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("MCP endpoint must be an origin URL")
    tools = payload.get("allowedTools", list((payload.get("tools") or {}).keys()))
    if not isinstance(tools, list) or not all(isinstance(tool, str) and tool.strip() for tool in tools):
        raise ValueError("invalid MCP allowlist")
    enabled, reviewed, version = payload["enabled"], payload["reviewed"], payload["version"]
    if not isinstance(enabled, bool) or not isinstance(reviewed, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("invalid MCP registry state")
    return GovernedMCPServer(name=name, transport=transport, endpoint=endpoint, profile=profile, allowed_tools=frozenset(tools), enabled=enabled, reviewed=reviewed, version=version)


__all__ = ["GovernedMCPServer", "MCPRegistry", "parse_server"]

class MCPRegistry:
    """In-memory active registry; applying a new response revokes removed versions."""

    def __init__(self) -> None:
        self._servers: dict[str, GovernedMCPServer] = {}

    def apply(self, records: list[dict[str, object]], *, profile: str) -> tuple[GovernedMCPServer, ...]:
        """Replace active definitions and return only eligible reviewed servers."""
        parsed = [parse_server(record) for record in records]
        self._servers = {server.name: server for server in parsed if server.profile == profile}
        return tuple(server for server in self._servers.values() if server.enabled and server.reviewed)

    def allowed(self, name: str, *, profile: str, tool: str) -> bool:
        """Re-check the current registry before every call."""
        server = self._servers.get(name)
        return server is not None and server.eligible(profile=profile, tool=tool)

    def revoke(self, name: str) -> None:
        """Immediately disable a server after a control-plane revoke."""
        self._servers.pop(name, None)
