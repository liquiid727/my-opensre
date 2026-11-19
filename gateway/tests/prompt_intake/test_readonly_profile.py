"""Restricted prompt lifecycle: capabilities survive no secret persistence or approval bypass."""

from __future__ import annotations

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.agent_harness import SessionCore, SessionManager
from core.agent_harness.session import InMemorySessionStore
from core.llm.types import ToolCall
from core.tool import ToolExecutionRequest
from gateway.core.prompt_intake import JsonlPromptJobStore, PromptQueue, PromptWorker, PromptState
from gateway.web import webapp
from infrastructure.turn_host.runtime_policy import TaskBinding, current_task_binding
from infrastructure.turn_host.unattended_session import UnattendedSessions, approval_question


def _binding(attempt: str = "attempt-1", resource: str = "host:1") -> dict[str, str]:
    return {"investigation_id": "inv-1", "attempt_id": attempt, "credential": "secret-capability",
            "resource_id": resource, "start": "2026-10-30T00:00:00Z", "end": "2026-10-30T00:30:00Z"}


@pytest.fixture
def restricted(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("OPENSRE_AGENT_PROFILE", "ops-admin-readonly")
    monkeypatch.setenv("OPENSRE_ALERT_LISTENER_TOKEN", "service-token")
    queue = PromptQueue()
    webapp.app.state.prompt_queue = queue
    yield queue, TestClient(webapp.app, client=("127.0.0.1", 40000), headers={"Authorization": "Bearer service-token"})
    del webapp.app.state.prompt_queue


def test_scope_pinning_answers_and_unknown_approval_are_fail_closed(restricted: Any) -> None:
    queue, client = restricted
    payload = {"prompt": "investigate", "actor": "user-1", "conversation": "new",
               "request_id": "request-0001", "ops_admin": _binding()}
    submitted = client.post("/v1/prompt", json=payload)
    assert submitted.status_code == HTTPStatus.ACCEPTED
    job = queue.get(submitted.json()["prompt_id"])
    assert job is not None
    queue.needs_input(job, "Which service?", choice={"interaction_kind": "user_question"})
    url = f"/v1/prompt/{job.id}/answer"
    answer = {"answer": "orders", "actor": "user-1", "request_id": "answer-0001", "ops_admin": _binding("attempt-2")}
    assert client.post(url, json={**answer, "ops_admin": _binding(resource="host:2")}).status_code == HTTPStatus.FORBIDDEN
    assert client.post(url, json={**answer, "actor": "user-2"}).status_code == HTTPStatus.FORBIDDEN
    queue.needs_input(job, "Approve?", choice={"interaction_kind": "tool_approval"})
    assert client.post(url, json={**answer, "answer": "Approve"}).status_code == HTTPStatus.FORBIDDEN
    queue.needs_input(job, "?", choice={"interaction_kind": "unrecognized"})
    assert client.post(url, json=answer).status_code == HTTPStatus.FORBIDDEN
    queue.needs_input(job, "Which service?", choice={"interaction_kind": "user_question"})
    first = client.post(url, json=answer)
    assert first.status_code == HTTPStatus.ACCEPTED
    assert client.post(url, json=answer).json()["prompt_id"] == first.json()["prompt_id"]
    assert queue.get(first.json()["prompt_id"]).readonly_scope["attempt_id"] == "attempt-2"
    continued = client.post("/v1/prompt", json={**payload, "conversation": job.session_id, "request_id": "request-0002"})
    assert continued.status_code == HTTPStatus.ACCEPTED


def test_worker_enforces_tools_and_never_generates_approval_or_persists_capability(
    restricted: Any, tmp_path: Path,
) -> None:
    store = JsonlPromptJobStore(tmp_path / "prompts.jsonl")
    queue = PromptQueue(store=store)
    binding = TaskBinding.from_payload(_binding())
    decisions: list[Any] = []

    class Runner:
        def run(self, text: str, session: SessionCore, output: Any, logger: Any, **kwargs: Any) -> object:
            assert current_task_binding() == binding
            assert binding.credential not in text
            for name, gated in (("shell", False), ("arbitrary_mcp", False), ("ops_admin_query_logs", True)):
                tool = type("Tool", (), {"requires_approval": gated})()
                request = ToolExecutionRequest(tool_call=ToolCall(id="call", name=name, input={}),
                                               tool=tool, arguments={}, source="test", resolved_integrations={})
                decisions.append(output.tool_hooks.before_tool_call(request))
            assert session.pending_user_choice is None
            session.pending_user_choice = approval_question("shell", {}, "danger", "")
            return object()

        def drop_session(self, session_id: str) -> None:
            pass

    worker = PromptWorker(queue, Runner(), logger=logging.getLogger(__name__),
                          sessions=UnattendedSessions(SessionManager(store=InMemorySessionStore())))
    job = queue.submit("investigate", context={}, actor="user-1", conversation="new", runtime_binding=binding)
    assert job is not None
    worker.run_one(job)
    assert all(decision.blocked and decision.terminate for decision in decisions)
    assert job.state is PromptState.FAILED and job.error_code == "readonly_interaction_forbidden"
    assert current_task_binding() is None
    assert binding.credential not in (tmp_path / "prompts.jsonl").read_text()
    assert binding.credential not in repr(job)
    restored = PromptQueue(store=store).get(job.id)
    assert restored is not None and restored.readonly_scope == binding.scope()
    assert restored.runtime_binding is None
    restored.state = PromptState.QUEUED
    worker.run_one(restored)
    assert restored.error_code == "task_capability_required"


def test_explicit_commands_and_unbound_submissions_cannot_dispatch(restricted: Any) -> None:
    queue, client = restricted
    assert client.post("/v1/prompt", json={"prompt": "hello"}).status_code == HTTPStatus.BAD_REQUEST
    assert client.post("/v1/prompt", json={"prompt": "hello", "ops_admin": _binding(), "conversation": "new"}).status_code == HTTPStatus.BAD_REQUEST
    class Runner:
        def run(self, *args: Any, **kwargs: Any) -> None:
            pytest.fail("literal slash command reached shared dispatch")
        def drop_session(self, session_id: str) -> None:
            pass
    job = queue.submit("/cron add --prompt evil", context={}, actor="user", conversation="new",
                       runtime_binding=TaskBinding.from_payload(_binding()))
    assert job is not None
    worker = PromptWorker(queue, Runner(), logger=logging.getLogger(__name__))
    worker.run_one(job)
    assert job.error_code == "readonly_command_forbidden"


def test_other_http_ingress_is_disabled_and_token_is_required(restricted: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _, client = restricted
    for path in ("/alerts", "/v1/loops/sync", "/investigate"):
        assert client.post(path, json={}).status_code == HTTPStatus.FORBIDDEN
    assert client.get("/v1/prompt/missing", headers={"Authorization": "Bearer wrong"}).status_code == HTTPStatus.UNAUTHORIZED
    monkeypatch.delenv("OPENSRE_ALERT_LISTENER_TOKEN")
    monkeypatch.delenv("OPENSRE_GATEWAY_LISTENER_TOKEN", raising=False)
    assert client.post("/v1/prompt", json={"prompt": "x"}).status_code == HTTPStatus.SERVICE_UNAVAILABLE
    monkeypatch.delenv("OPENSRE_AGENT_PROFILE")
    assert client.post("/v1/prompt", json={"prompt": "x", "ops_admin": _binding()}).status_code == HTTPStatus.FORBIDDEN


def test_dedicated_gateway_never_starts_other_execution_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    from gateway.core.lifecycle.controller import _gateway_hosts_scheduler
    from gateway.startup import start_gateway
    from gateway.web.startup import WebStartup

    monkeypatch.setenv("OPENSRE_AGENT_PROFILE", "ops-admin-readonly")
    monkeypatch.setenv("OPENSRE_GATEWAY_HOST_SCHEDULER", "true")
    monkeypatch.setattr("gateway.startup.start_web_server", lambda **kwargs: WebStartup(server=None, status="test"))
    def forbidden(**kwargs: Any) -> None:
        pytest.fail("restricted gateway started a chat execution host")
    monkeypatch.setattr("gateway.startup.start_transports", forbidden)
    gateway = start_gateway(logger=logging.getLogger(__name__), handler=forbidden)
    assert gateway.transports == {}
    assert _gateway_hosts_scheduler() is False
