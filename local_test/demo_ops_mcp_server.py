"""Local demo MCP server with one read tool and one write tool.

The write tool exists to exercise the approval gate: Ops Admin must never run it
from an agent request, only after a different human approves the pending call.
The tool itself writes to a local marker file so the demo can prove whether the
external server was actually contacted.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

app = MCPServer("opensre-demo-ops")
MARKER = Path(os.environ.get("DEMO_MCP_MARKER", "/tmp/opensre-demo-mcp-writes.log"))


@app.tool()
def read_service_status(resource: str) -> dict[str, str]:
    """Return bounded status for the demo host only."""
    if resource != "host:1":
        return {"status": "denied", "resource": resource}
    return {"status": "degraded", "resource": resource, "source": "demo-mcp"}


@app.tool()
def restart_test_service(resource: str, service: str) -> dict[str, str]:
    """Restart one test service. This is a write operation and needs approval."""
    if resource != "host:1":
        return {"status": "denied", "resource": resource}
    if service not in {"orders", "payment"}:
        return {"status": "rejected", "reason": "unknown service"}
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    with MARKER.open("a", encoding="utf-8") as handle:
        handle.write(f"{resource} {service}\n")
    return {"status": "restarted", "resource": resource, "service": service}


if __name__ == "__main__":
    app.run(transport="stdio")
