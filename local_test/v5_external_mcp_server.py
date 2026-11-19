"""External streamable-HTTP MCP fixture for the V5 acceptance flow."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer


app = MCPServer("opensre-v5-external-fixture")


def _count_call() -> None:
    counter = os.environ.get("V5_EXTERNAL_MCP_COUNTER_FILE", "").strip()
    if not counter:
        return
    path = Path(counter)
    try:
        current = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    except (OSError, ValueError):
        current = 0
    path.write_text(json.dumps(current + 1), encoding="utf-8")


@app.tool()
def read_status(resource: str) -> dict[str, str]:
    """Return bounded status for the explicitly configured fixture host."""
    _count_call()
    if resource != "host:1":
        return {"status": "denied", "resource": resource}
    return {"status": "healthy", "resource": resource, "source": "external-mcp"}


if __name__ == "__main__":
    app.run(
        transport="streamable-http",
        host=os.environ.get("V5_EXTERNAL_MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("V5_EXTERNAL_MCP_PORT", "18100")),
        streamable_http_path=os.environ.get("V5_EXTERNAL_MCP_PATH", "/mcp"),
        stateless_http=True,
    )
