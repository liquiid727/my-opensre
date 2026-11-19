"""Tiny read-only MCP server used by the V5 local acceptance flow."""

from mcp.server.mcpserver import MCPServer

app = MCPServer("opensre-v5-fixture")


@app.tool()
def read_status(resource: str) -> dict[str, str]:
    """Return bounded status for the fixture host only."""
    if resource != "host:1":
        return {"status": "denied", "resource": resource}
    return {"status": "healthy", "resource": resource, "source": "fixture-mcp"}


if __name__ == "__main__":
    app.run(transport="stdio")
