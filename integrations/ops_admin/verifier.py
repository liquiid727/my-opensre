"""Task-scoped authorization verification (health alone is insufficient)."""

from __future__ import annotations

from infrastructure.turn_host.runtime_policy import TaskBinding
from integrations.ops_admin.client import OpsAdminClient


def verify_task(client: OpsAdminClient, binding: TaskBinding) -> bool:
    """Validate the current task against the authoritative backend."""
    result = client.verify(binding)
    return not result.get("error") and result.get("valid") is True
