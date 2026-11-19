"""Environment acceptance for an external MCP and resource revocation.

The script starts a real streamable-HTTP MCP process, the disposable Ops Admin
fixture, and the real OpenSRE governed MCP route. It then performs a successful
investigation-scoped call followed by MCP revocation, resource revocation, and
resource-mismatch calls. A counter in the external process proves denied calls
never reach the external MCP.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from threading import Thread
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI

from gateway.web.ops_admin_mcp_routes import router as mcp_router


ROOT = Path(__file__).resolve().parents[2]
OPS_ADMIN_DIR = Path(os.environ.get("OPS_ADMIN_DIR", ROOT / "ops-admin" / "backend")).resolve()
OPS_ADMIN_URL = os.environ.get("V5_OPS_ADMIN_URL", "http://127.0.0.1:18082")
GATEWAY_URL = os.environ.get("V5_GATEWAY_URL", "http://127.0.0.1:18084")
MCP_URL = os.environ.get("V5_EXTERNAL_MCP_URL", "http://127.0.0.1:18100/mcp")
SERVICE_TOKEN = os.environ.get("V5_SERVICE_TOKEN", "local-v5-mcp-token")


def _wait_port(url: str, timeout: float = 60.0, process: subprocess.Popen[bytes] | None = None) -> None:
    parsed = httpx.URL(url)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((parsed.host, parsed.port or 80), timeout=0.5):
                return
        except OSError:
            if process is not None and process.poll() is not None:
                detail = process.stderr.read().decode(errors="replace") if process.stderr else ""
                raise RuntimeError(f"service exited with {process.returncode}: {detail}")
            time.sleep(0.1)
    raise RuntimeError(f"service did not listen: {url}")


def _call(client: httpx.Client, investigation: dict[str, object], **overrides: object) -> httpx.Response:
    end = datetime.now(UTC).replace(microsecond=0)
    payload = {
        "version": 1,
        "tool": "read_status",
        "arguments": {"resource": "host:1"},
        "profile": "ops-admin-readonly",
        "environment": "test",
        "resourceType": "host",
        "resourceId": 1,
        "investigationId": investigation["id"],
        "attemptId": investigation["attemptId"],
        "toolCallId": str(uuid4()),
        "start": (end - timedelta(minutes=5)).isoformat(),
        "end": end.isoformat(),
    }
    payload.update(overrides)
    return client.post(
        f"{OPS_ADMIN_URL}/api/v1/internal/ai-mcp/call",
        json={"userId": 1, "serverId": 9, "input": payload},
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}", "X-Service-ID": "opensre"},
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="opensre-v5-mcp-") as temporary:
        counter = Path(temporary) / "external.calls"
        external_env = os.environ.copy()
        external_env.update(
            V5_EXTERNAL_MCP_COUNTER_FILE=str(counter),
            V5_EXTERNAL_MCP_PORT="18100",
        )
        external = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("v5_external_mcp_server.py"))],
            env=external_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        fixture_env = os.environ.copy()
        fixture_env.update(
            INVESTIGATION_FIXTURE_MCP_ENDPOINT=MCP_URL,
            INVESTIGATION_FIXTURE_MCP_TRANSPORT="streamable_http",
            INVESTIGATION_FIXTURE_DISABLE_WORKER="true",
            OPS_ADMIN_OPENSRE_URL=GATEWAY_URL,
            OPS_ADMIN_OPENSRE_SERVICE_TOKEN=SERVICE_TOKEN,
            OPS_ADMIN_OPENSRE_TOKEN="local-v5-query-token",
            OPS_ADMIN_INVESTIGATION_QUERY_KEY="local-v5-investigation-query-key-0123456789abcdef",
            OPS_ADMIN_MCP_ENABLED="true",
            OPS_ADMIN_INVESTIGATIONS_ENABLED="true",
        )
        fixture = subprocess.Popen(
            ["go", "run", "./cmd/investigation-fixture"],
            cwd=OPS_ADMIN_DIR,
            env=fixture_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                FastAPI(), host="127.0.0.1", port=18084, log_level="warning"
            )
        )
        app = server.config.app
        app.include_router(mcp_router)
        os.environ.update(
            OPS_ADMIN_URL=OPS_ADMIN_URL,
            OPS_ADMIN_OPENSRE_SERVICE_TOKEN=SERVICE_TOKEN,
            OPS_ADMIN_MCP_ENABLED="true",
        )
        thread = Thread(target=server.run, daemon=True)
        thread.start()
        try:
            _wait_port(MCP_URL)
            _wait_port(OPS_ADMIN_URL, process=fixture)
            deadline = time.monotonic() + 30
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("governed gateway did not start")
            with httpx.Client(timeout=10, trust_env=False) as client:
                created = client.post(
                    f"{OPS_ADMIN_URL}/api/v1/ai-investigations",
                    headers={"X-Test-User": "1"},
                    json={
                        "question": "external MCP acceptance",
                        "environment": "test",
                        "resourceType": "host",
                        "resourceId": 1,
                        "profileId": 1,
                        "start": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                        "end": datetime.now(UTC).isoformat(),
                        "idempotencyKey": str(uuid4()),
                    },
                )
                if created.status_code != HTTPStatus.OK:
                    raise RuntimeError(f"investigation create failed: {created.status_code} {created.text}")
                investigation = created.json()["data"]
                first = _call(client, investigation)
                first_data = first.json().get("data", {})
                if first.status_code != HTTPStatus.OK or first_data.get("structured_content", {}).get("status") != "healthy":
                    raise RuntimeError(f"external MCP call failed: {first.status_code} {first.text}")
                if not first_data.get("evidence_id"):
                    raise RuntimeError("external MCP evidence was not persisted")

                client.post(f"{OPS_ADMIN_URL}/__fixture/mcp-revoke", headers={"X-Test-User": "1"})
                revoked = _call(client, investigation)
                if revoked.status_code != HTTPStatus.FORBIDDEN:
                    raise RuntimeError(f"MCP revoke was not enforced: {revoked.status_code} {revoked.text}")
                client.post(f"{OPS_ADMIN_URL}/__fixture/mcp-restore", headers={"X-Test-User": "1"})
                client.post(f"{OPS_ADMIN_URL}/__fixture/revoke", headers={"X-Test-User": "1"})
                resource_revoked = _call(client, investigation)
                if resource_revoked.status_code != HTTPStatus.FORBIDDEN:
                    raise RuntimeError(f"resource revoke was not enforced: {resource_revoked.status_code} {resource_revoked.text}")
                wrong_resource = _call(client, investigation, resourceId=2)
                if wrong_resource.status_code != HTTPStatus.FORBIDDEN:
                    raise RuntimeError(f"resource mismatch was not enforced: {wrong_resource.status_code} {wrong_resource.text}")
                calls = int(counter.read_text(encoding="utf-8"))
                if calls != 1:
                    raise RuntimeError(f"denied calls reached external MCP: {calls}")
                print(json.dumps({"status": "passed", "external_mcp_calls": calls, "investigation": investigation["id"]}))
        finally:
            server.should_exit = True
            for process in (fixture, external):
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
