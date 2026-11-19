"""V5 live-model acceptance through the real OpenSRE agent client.

Prerequisites:

* start the Ops Admin investigation fixture with
  ``INVESTIGATION_FIXTURE_MCP_COMMAND=$PWD/.venv/bin/python`` and
  ``INVESTIGATION_FIXTURE_MCP_ARGS='[".../local_test/v5_mcp_server.py"]'``;
* configure one real LLM provider (or an OpenAI-compatible test endpoint) in
  the normal OpenSRE environment;
* set ``OPS_ADMIN_OPENSRE_SERVICE_TOKEN`` and ``OPS_ADMIN_MCP_ENABLED=true``.

This script does not replace model inference. It runs the normal ``TurnRunner``
and LLM client, then checks that the model selected the reviewed MCP tool and
that Ops Admin persisted MCP evidence. Without a configured model it exits with
an explicit unmet-prerequisite message.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from threading import Thread
from typing import Any
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import ValidationError
from rich.console import Console

from config.llm_settings import LLMSettings
from gateway.core.chat_agent_build import chat_agent_build_config
from gateway.core.prompt_intake import PromptQueue, PromptWorker
from gateway.web.ops_admin_mcp_routes import router as mcp_router
from gateway.web.prompt_routes import router as prompt_router
from infrastructure.turn_host.unattended_session import UnattendedSessions
from core.agent_harness import SessionManager
from core.agent_harness.session import InMemorySessionStore
from infrastructure.turn_host.turn_runner import TurnRunner


GATEWAY_URL = os.environ.get("V5_GATEWAY_URL", "http://127.0.0.1:18084")
OPS_ADMIN_URL = os.environ.get("OPS_ADMIN_URL", "http://127.0.0.1:18082")


def _require_model() -> None:
    try:
        settings = LLMSettings.from_env()
    except ValidationError as exc:
        raise SystemExit(
            "V5 live-model acceptance requires a configured OpenSRE LLM provider; "
            f"configuration is not ready: {exc.errors()[0]['type']}"
        ) from None
    credential_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "trustedrouter": "TRUSTEDROUTER_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "groq": "GROQ_API_KEY",
        "azure-openai": "AZURE_OPENAI_API_KEY",
        "custom-openai": "CUSTOM_OPENAI_API_KEY",
        "custom-anthropic": "CUSTOM_ANTHROPIC_API_KEY",
    }.get(settings.provider)
    if credential_env and not os.environ.get(credential_env, "").strip():
        raise SystemExit(
            "V5 live-model acceptance requires a real model credential; "
            f"set {credential_env} for provider {settings.provider!r}."
        )


def main() -> None:
    _require_model()
    os.environ.setdefault("OPENSRE_AGENT_PROFILE", "ops-admin-readonly")
    os.environ.setdefault("OPS_ADMIN_URL", OPS_ADMIN_URL)
    os.environ.setdefault("OPS_ADMIN_MCP_ENABLED", "true")
    os.environ.setdefault("OPS_ADMIN_MCP_SERVICE_TOKEN", "local-v5-mcp-token")
    os.environ.setdefault("OPENSRE_GATEWAY_LISTENER_TOKEN", "local-v5-listener-token")

    queue = PromptQueue()
    runner = TurnRunner(
        console=Console(force_terminal=False),
        agent_build=chat_agent_build_config(hosts_scheduler=False),
    )
    worker = PromptWorker(
        queue,
        runner,
        logger=logging.getLogger("v5-live-model"),
        sessions=UnattendedSessions(SessionManager(store=InMemorySessionStore())),
    )
    app = FastAPI()
    app.include_router(prompt_router)
    app.include_router(mcp_router)
    app.state.prompt_queue = queue
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18084, log_level="warning"))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    worker.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() >= deadline:
            raise SystemExit("V5 gateway fixture did not start")
        time.sleep(0.05)

    end = datetime.now(UTC).replace(microsecond=0)
    payload: dict[str, Any] = {
        "question": "Use the reviewed MCP read_status tool for host:1, then report the observed status and source.",
        "environment": "test",
        "resourceType": "host",
        "resourceId": 1,
        "profileId": 1,
        "start": (end - timedelta(minutes=30)).isoformat(),
        "end": end.isoformat(),
        "idempotencyKey": str(uuid4()),
    }
    headers = {"X-Test-User": "1"}
    with httpx.Client(timeout=10, trust_env=False, headers=headers) as client:
        created = client.post(f"{OPS_ADMIN_URL}/api/v1/ai-investigations", json=payload)
        if created.status_code != HTTPStatus.OK:
            raise SystemExit(f"investigation create failed: {created.status_code} {created.text}")
        investigation = created.json()["data"]
        investigation_id = investigation["id"]
        result: dict[str, Any] = {}
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            response = client.get(f"{OPS_ADMIN_URL}/api/v1/ai-investigations/{investigation_id}")
            if response.status_code != HTTPStatus.OK:
                raise SystemExit(f"investigation read failed: {response.status_code} {response.text}")
            result = response.json()["data"]
            status = result["investigation"]["status"]
            if status in {"SUCCEEDED", "FAILED", "CANCELLED", "SUBMIT_UNKNOWN"}:
                break
            time.sleep(0.5)
        else:
            raise SystemExit("live model investigation timed out")

    if result["investigation"]["status"] != "SUCCEEDED":
        raise SystemExit(f"live model did not complete: {result['investigation']['status']}")
    evidence = result.get("evidence", [])
    if not any(str(item.get("source", "")).startswith("mcp:") for item in evidence):
        raise SystemExit(f"MCP evidence was not persisted: {evidence!r}")
    print({"status": "passed", "investigation": investigation_id, "mcp_evidence": len(evidence)})
    server.should_exit = True
    worker.stop(timeout_seconds=5)


if __name__ == "__main__":
    main()
