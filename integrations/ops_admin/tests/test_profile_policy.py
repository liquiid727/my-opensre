"""Published tool sets and live revocations survive previously discovered tools."""

import json
from dataclasses import replace
from http import HTTPStatus

import httpx

from infrastructure.turn_host.runtime_policy import bound_task_binding
from integrations.ops_admin.client import OpsAdminClient
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.tests.test_readonly_tools import binding
from integrations.ops_admin.tools.provider import OpsAdminToolProvider


def test_published_tools_limits_and_live_revocation() -> None:
    trusted = replace(binding(), profile_id="1", profile_version="2")
    allowed = ["ops_admin_query_logs"]
    queries = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/verify"):
            return httpx.Response(
                HTTPStatus.OK,
                json={
                    "valid": True,
                    "policy": {
                        "profile_id": "1",
                        "version": "2",
                        "model_ref": "opensre-default",
                        "instructions": "Review logs",
                        "native_tools": allowed,
                        "max_tool_calls": 2,
                        "query_timeout_seconds": 10,
                        "task_timeout_seconds": 120,
                        "max_output_bytes": 1024,
                    },
                },
            )
        queries.append(request)
        return httpx.Response(HTTPStatus.OK, json={"available": True, "evidence_id": 42})

    client = OpsAdminClient(
        OpsAdminConfig("http://platform.test"), transport=httpx.MockTransport(respond)
    )
    provider = OpsAdminToolProvider(client)
    with bound_task_binding(trusted):
        tools = provider.action_tools(confirm_fn=None, is_tty=False)
        assert [t.name for t in tools] == allowed
        scope = {k: v for k, v in trusted.scope().items() if not k.startswith("profile_")}
        assert tools[0](**scope)["evidence_id"] == 42
        allowed.clear()
        assert tools[0](**scope)["error"] == "profile_limit_or_revocation"
        allowed.append("ops_admin_query_logs")
        assert tools[0](**scope)["evidence_id"] == 42
        assert tools[0](**scope)["error"] == "profile_limit_or_revocation"
        assert len(queries) == 2
        assert trusted.credential not in json.dumps(tools[0].public_input_schema)
    assert (
        trusted.scope()
        == trusted.from_payload({**trusted.scope(), "credential": trusted.credential}).scope()
    )
