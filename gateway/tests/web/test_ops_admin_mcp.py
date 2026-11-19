"""Keep MCP service authentication independent of the investigation listener."""

from http import HTTPStatus

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.web.ops_admin_mcp_routes import router
from gateway.web.prompt_routes import router as prompt_router


def test_mcp_requires_its_service_token_even_from_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENSRE_GATEWAY_LISTENER_TOKEN", "investigation-test-token")
    monkeypatch.setenv("OPS_ADMIN_OPENSRE_SERVICE_TOKEN", "mcp-test-token")
    monkeypatch.delenv("OPENSRE_ALERT_LISTENER_TOKEN", raising=False)
    monkeypatch.setenv("OPS_ADMIN_MCP_ENABLED", "false")
    app = FastAPI()
    app.include_router(router)
    app.include_router(prompt_router)
    with TestClient(app, client=("127.0.0.1", 40000), base_url="http://127.0.0.1") as client:
        accepted = client.post(
            "/v1/ops-admin/mcp/discover",
            json={},
            headers={"Authorization": "Bearer mcp-test-token"},
        )
        assert accepted.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert accepted.json()["error"] == "mcp_disabled"
        for token in ("", "investigation-test-token", "wrong-token"):
            denied = client.post(
                "/v1/ops-admin/mcp/discover",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert denied.status_code == HTTPStatus.UNAUTHORIZED

        prompt = client.post(
            "/v1/prompt", json={}, headers={"Authorization": "Bearer mcp-test-token"}
        )
        assert prompt.status_code == HTTPStatus.UNAUTHORIZED

        monkeypatch.delenv("OPS_ADMIN_OPENSRE_SERVICE_TOKEN")
        missing = client.post("/v1/ops-admin/mcp/discover", json={})
        assert missing.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert missing.json()["error"] == "mcp_service_token_required"
