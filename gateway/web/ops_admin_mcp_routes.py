"""Trusted Ops Admin MCP ingress; never registers tools in the readonly agent."""

from __future__ import annotations

import hmac
import logging
import os
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from config.constants.ops_admin import OPS_ADMIN_MCP_ENABLED_ENV, OPS_ADMIN_MCP_SERVICE_TOKEN_ENV
from integrations.ops_admin.config import OpsAdminConfig
from integrations.ops_admin.mcp_runtime import GovernedMCPRuntime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/ops-admin/mcp/{action}")
async def governed_mcp(action: str, request: Request) -> JSONResponse:
    """Only trusted control-plane callers can request a versioned discover/call."""
    expected = os.environ.get(OPS_ADMIN_MCP_SERVICE_TOKEN_ENV, "").strip()
    if not expected:
        return JSONResponse(
            {"error": "mcp_service_token_required"}, status_code=HTTPStatus.SERVICE_UNAVAILABLE
        )
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
        return JSONResponse({"error": "unauthorized"}, status_code=HTTPStatus.UNAUTHORIZED)
    if os.environ.get(OPS_ADMIN_MCP_ENABLED_ENV) != "true":
        return JSONResponse({"error": "mcp_disabled"}, status_code=HTTPStatus.SERVICE_UNAVAILABLE)
    try:
        body = await request.body()
        if len(body) > 65536:
            raise ValueError("oversized request")
        payload: dict[str, Any] = await request.json()
        server_id, version = payload["serverId"], payload["version"]
        if type(server_id) is not int or type(version) is not int:
            raise ValueError("invalid version")
        runtime = GovernedMCPRuntime(OpsAdminConfig.from_env())
        if action == "discover":
            result = await run_in_threadpool(runtime.discover, server_id, version)
        elif action == "call":
            result = await run_in_threadpool(
                runtime.call,
                server_id,
                version,
                payload["tool"],
                payload["arguments"],
                profile=payload["profile"],
                environment=payload["environment"],
                resource_type=payload["resourceType"],
                resource_id=payload["resourceId"],
                resource_namespace=payload.get("resourceNamespace", ""),
                resource_kind=payload.get("resourceKind", ""),
                resource_name=payload.get("resourceName", ""),
            )
        else:
            raise ValueError("invalid action")
        return JSONResponse(result)
    except Exception:
        logger.exception("Governed MCP request failed")
        return JSONResponse({"error": "mcp_request_rejected"}, status_code=HTTPStatus.BAD_GATEWAY)
