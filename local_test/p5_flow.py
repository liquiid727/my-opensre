"""Local cross-service acceptance: real SQLite/Go HTTP and Python queue/worker/tools.

Run the Ops Admin investigation-fixture on :18082 first, pointing its OpenSRE
URL at :18084 and using any nonempty test token. Then run this module from the
OpenSRE repository. No production services or external messages are used.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.agent_harness import SessionCore, SessionManager
from core.agent_harness.session import InMemorySessionStore
from core.agent_harness.session.pending_choice import PendingUserChoice
from core.llm.types import ToolCall
from core.tool.execution import execute_tool_calls
from local_test.p5_restart import verify_process_restart
from gateway.core.prompt_intake import PromptQueue, PromptWorker
from gateway.web.prompt_routes import router
from infrastructure.turn_host.runtime_policy import current_task_binding
from infrastructure.turn_host.unattended_session import UnattendedSessions
from integrations.ops_admin.client import OpsAdminClient
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.tools.provider import OpsAdminToolProvider


class ControlledRunner:
    """Replace model inference only; preserve real worker, tools and backend HTTP."""

    def __init__(self) -> None:
        self.mode = "complete"
        self.calls = 0
        self.secrets: set[str] = set()
        self.paused = threading.Event()
        self.resume = threading.Event()
        self.revocation_checked = threading.Event()

    def run(
        self,
        text: str,
        session: SessionCore,
        output: Any,
        logger: Any,
        *,
        slot_wait_seconds: float | None = None,
    ) -> object:
        _ = logger, slot_wait_seconds
        binding = current_task_binding()
        assert binding is not None
        self.secrets.add(binding.credential)
        assert binding.credential not in text
        provider = OpsAdminToolProvider(OpsAdminClient(OpsAdminConfig("http://127.0.0.1:18082")))
        tools = provider.action_tools(confirm_fn=None, is_tty=False)
        assert len(tools) == 4
        for forbidden in ("shell_run", "kubernetes_apply", "mcp_unreviewed"):
            refused = execute_tool_calls(
                [ToolCall(id="denied", name=forbidden, input={})], tools, {}
            )
            assert refused[0].is_error
        results = []
        for tool in tools:
            assert binding.credential not in json.dumps(tool.public_input_schema)
            assert tool(**{**binding.scope(), "resource_id": "99999"})["error"] == "scope_rejected"
            assert (
                tool(**{**binding.scope(), "query": "select secret"})["error"] == "scope_rejected"
            )
            execution = execute_tool_calls(
                [ToolCall(id=str(uuid4()), name=tool.name, input=binding.scope())], tools, {}
            )
            assert not execution[0].is_error
            result = execution[0].details
            assert isinstance(result, dict)
            assert not result.get("error"), result
            if self.mode == "unavailable" and tool.name in {
                "ops_admin_query_metrics",
                "ops_admin_query_logs",
            }:
                evidence = result.get("data", result)
                if isinstance(evidence, dict) and "available" in evidence:
                    assert evidence["available"] is False, result
                    assert evidence.get("missing_reason"), result
                else:
                    assert result.get("available") is False, result
            results.append(result)
        if self.mode == "revocation":
            self.paused.set()
            assert self.resume.wait(15), "permission revocation control timed out"
            for tool in tools:
                result = tool(**binding.scope())
                assert result.get("error") == "query_rejected", result
            self.revocation_checked.set()
            output.finalize("Current resource permission revoked; no further evidence can be read.")
            return object()
        self.calls += 1
        if self.mode == "question":
            session.pending_user_choice = PendingUserChoice(
                title="Which symptom?", options=("errors", "latency")
            )
        output.finalize(json.dumps({"analysis": "Controlled investigation", "evidence": results}))
        return object()

    def drop_session(self, session_id: str) -> None:
        """No pooled model instances in this controlled runner."""


def main() -> None:
    os.environ["OPENSRE_AGENT_PROFILE"] = "ops-admin-readonly"
    queue = PromptQueue()
    runner = ControlledRunner()
    worker = PromptWorker(
        queue,
        runner,
        logger=logging.getLogger("p5"),
        sessions=UnattendedSessions(SessionManager(store=InMemorySessionStore())),
    )
    app = FastAPI()
    app.include_router(router)
    app.state.prompt_queue = queue
    app.state.drop_submit = False
    app.state.dropped = 0

    @app.middleware("http")
    async def drop_accepted_response(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        if request.method == "POST" and request.url.path == "/v1/prompt" and app.state.drop_submit:
            app.state.drop_submit = False
            app.state.dropped += 1
            return JSONResponse(
                {"error": "simulated_lost_response"}, status_code=HTTPStatus.GATEWAY_TIMEOUT
            )
        return response

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18084, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    worker.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "gateway fixture did not start"
        time.sleep(0.05)
    checks: list[str] = []
    api = "http://127.0.0.1:18082/api/v1/ai-investigations"
    with httpx.Client(timeout=10, trust_env=False, headers={"X-Test-User": "1"}) as client:

        def create() -> dict[str, Any]:
            end = datetime.now(UTC).replace(microsecond=0)
            payload = {
                "question": "Investigate test orders",
                "environment": "test",
                "resourceType": "host",
                "resourceId": 1,
                "start": (end - timedelta(minutes=30)).isoformat(),
                "end": end.isoformat(),
                "idempotencyKey": str(uuid4()),
            }
            result = client.post(api, json=payload)
            assert result.status_code == HTTPStatus.OK, result.text
            inv = result.json()["data"]
            repeated = client.post(api, json=payload)
            assert repeated.json()["data"]["id"] == inv["id"]
            conflict = client.post(api, json={**payload, "question": "different"})
            assert conflict.status_code == HTTPStatus.CONFLICT
            return inv

        def detail(inv: dict[str, Any]) -> dict[str, Any]:
            response = client.get(f"{api}/{inv['id']}")
            assert response.status_code == HTTPStatus.OK, response.text
            return response.json()["data"]

        def wait(inv: dict[str, Any], states: set[str]) -> dict[str, Any]:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                result = detail(inv)
                if result["investigation"]["status"] in states:
                    return result
                time.sleep(0.1)
            raise AssertionError(f"task did not reach {states}: {result}")

        inv = create()
        completed = wait(inv, {"SUCCEEDED"})
        assert len(completed["evidence"]) == 4
        assert all(e["resourceId"] == 1 for e in completed["evidence"])
        checks += [
            "create-complete-four-real-tool-queries",
            "user-idempotency-conflict",
            "model-scope-and-arbitrary-query-rejected",
        ]
        foreign = client.get(f"{api}/{inv['id']}", headers={"X-Test-User": "2"})
        assert foreign.status_code == HTTPStatus.FORBIDDEN
        checks.append("cross-user-task-denied")
        serialized = json.dumps(completed)
        assert all(secret not in serialized for secret in runner.secrets)
        for secret in (
            "sensitive-label-never-expose",
            "SECRET summary never expose",
            "192.0.2.2",
            "private-test",
        ):
            assert secret not in serialized
        checks.append("credential-absent-model-and-user-result")

        app.state.drop_submit = True
        calls_before = runner.calls
        unknown = create()
        wait(unknown, {"SUBMIT_UNKNOWN"})
        recovered = wait(unknown, {"SUCCEEDED"})
        assert len(recovered["attempts"]) == 1
        assert runner.calls == calls_before + 1
        assert app.state.dropped == 1
        checks.append("accepted-response-loss-stable-request-reconciliation")

        runner.mode = "question"
        parked = create()
        waiting = wait(parked, {"WAITING_INPUT"})["investigation"]
        assert waiting["interactionKind"] == "user_question"
        cancelled = client.post(
            f"{api}/{parked['id']}/cancel", json={"version": waiting["version"]}
        )
        assert cancelled.status_code == HTTPStatus.OK, cancelled.text
        assert detail(parked)["investigation"]["status"] == "CANCELLED"
        rejected = client.post(
            f"{api}/{parked['id']}/answers",
            json={
                "version": waiting["version"],
                "answer": "errors",
                "idempotencyKey": str(uuid4()),
            },
        )
        assert rejected.status_code == HTTPStatus.CONFLICT
        checks.append("waiting-input-cancel-no-followup")

        raced = create()
        waiting = wait(raced, {"WAITING_INPUT"})["investigation"]
        runner.mode = "complete"
        payload = {
            "version": waiting["version"],
            "answer": "errors",
            "idempotencyKey": str(uuid4()),
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(
                pool.map(
                    lambda action: client.post(f"{api}/{raced['id']}/{action}", json=payload),
                    ["answers", "cancel"],
                )
            )
        assert sorted(r.status_code for r in replies) == [HTTPStatus.OK, HTTPStatus.CONFLICT], [
            r.text for r in replies
        ]
        final = wait(raced, {"SUCCEEDED", "CANCELLED"})
        assert len(final["attempts"]) in {1, 2}
        checks.append("answer-cancel-version-race-single-path")

        runner.mode = "revocation"
        revoked = create()
        assert runner.paused.wait(15), "investigation did not reach revocation barrier"
        assert (
            client.post("http://127.0.0.1:18082/__fixture/revoke").status_code
            == HTTPStatus.NO_CONTENT
        )
        runner.resume.set()
        # Permission loss also hides task details; restore only after the worker settled.
        assert runner.revocation_checked.wait(15), "revoked query did not reject"
        assert client.get(f"{api}/{revoked['id']}").status_code == HTTPStatus.FORBIDDEN
        assert (
            client.post("http://127.0.0.1:18082/__fixture/restore").status_code
            == HTTPStatus.NO_CONTENT
        )
        wait(revoked, {"SUCCEEDED"})
        checks.append("runtime-permission-revocation-denies-every-tool")

        runner.mode = "unavailable"
        assert (
            client.post("http://127.0.0.1:18082/__fixture/sources-down").status_code
            == HTTPStatus.NO_CONTENT
        )
        missing = wait(create(), {"SUCCEEDED"})
        unavailable_evidence = [
            e for e in missing["evidence"] if e["source"] in {"metrics", "logs"}
        ]
        assert len(unavailable_evidence) == 2 and all(
            e["available"] is False for e in unavailable_evidence
        )
        checks.append("source-outage-explicit-missing-evidence")

        del app.state.prompt_queue
        unavailable = httpx.post(
            "http://127.0.0.1:18084/v1/prompt",
            json={"prompt": "unavailable"},
            headers={"Authorization": f"Bearer {os.environ['OPENSRE_GATEWAY_LISTENER_TOKEN']}"},
        )
        assert unavailable.status_code == HTTPStatus.SERVICE_UNAVAILABLE, unavailable.text
        app.state.prompt_queue = queue
        checks.append("web-without-prompt-queue-unavailable")
        server.should_exit = True
        worker.stop(timeout_seconds=10)
        thread.join(timeout=10)
        verify_process_restart(create, wait)
        checks.append("gateway-process-kill-restart-interrupted-no-replay")
    print(
        json.dumps(
            {
                "passed": checks,
                "remaining": ["real model and external test datasource compatibility"],
                "model": "controlled runner",
                "database": "Go fixture SQLite",
                "completed_tool_batches": runner.calls,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
