"""Kill an actual gateway fixture process and verify durable interruption over HTTP."""

from __future__ import annotations

import logging
import multiprocessing
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import uvicorn
from fastapi import FastAPI

from core.agent_harness import SessionManager
from core.agent_harness.session import InMemorySessionStore
from gateway.core.prompt_intake import JsonlPromptJobStore, PromptQueue, PromptWorker
from gateway.web.prompt_routes import router
from infrastructure.turn_host.unattended_session import UnattendedSessions


class BlockingRunner:
    """Record admission, then await process termination without any external action."""

    def __init__(self, marker: str) -> None:
        self.marker = Path(marker)

    def run(self, *_args: Any, **_kwargs: Any) -> object:
        with self.marker.open("a") as handle:
            handle.write("admitted\n")
        while True:
            time.sleep(0.1)

    def drop_session(self, session_id: str) -> None:
        """No model sessions are allocated by this runner."""


def _gateway_process(store: str, marker: str, ready: Any) -> None:
    queue = PromptQueue(store=JsonlPromptJobStore(Path(store)), stale_seconds=0)
    worker = PromptWorker(
        queue,
        BlockingRunner(marker),
        logger=logging.getLogger("p5-restart"),
        sessions=UnattendedSessions(SessionManager(store=InMemorySessionStore())),
    )
    app = FastAPI()
    app.include_router(router)
    app.state.prompt_queue = queue
    worker.start()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18084, log_level="warning"))

    # The parent probes the port after this signal; uvicorn binds immediately
    # when run below, and the subsequent HTTP request is the readiness check.
    ready.set()
    server.run()


def verify_process_restart(
    create: Callable[[], dict[str, Any]],
    wait: Callable[[dict[str, Any], set[str]], dict[str, Any]],
) -> None:
    """The same backend attempt becomes INTERRUPTED and never re-enters a runner."""
    context = multiprocessing.get_context("spawn")
    with TemporaryDirectory(prefix="opensre-p5-restart-") as temporary:
        store = str(Path(temporary) / "jobs.jsonl")
        marker = Path(temporary) / "admissions.txt"

        def start() -> Any:
            ready = context.Event()
            process = context.Process(target=_gateway_process, args=(store, str(marker), ready))
            process.start()
            if not ready.wait(20):
                process.kill()
                process.join(10)
                raise AssertionError("gateway child did not become ready")
            return process

        process = start()
        try:
            investigation = create()
            wait(investigation, {"RUNNING"})
            deadline = time.monotonic() + 10
            while not marker.exists():
                assert time.monotonic() < deadline, "runner did not start"
                time.sleep(0.05)
            process.kill()
            process.join(10)
            process = start()
            result = wait(investigation, {"INTERRUPTED"})
            assert len(result["attempts"]) == 1, result
            assert marker.read_text().splitlines() == ["admitted"], "interrupted work replayed"
            assert "credential" not in Path(store).read_text(), "secret persisted in job store"
        finally:
            if process.is_alive():
                process.kill()
            process.join(10)
