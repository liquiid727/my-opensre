"""Trusted, transient task scope for restricted hosted turns."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config.constants.ops_admin import (
    OPS_ADMIN_INVESTIGATOR_PROFILE,
    OPS_ADMIN_PROFILE_ENV,
    OPS_ADMIN_READONLY_PROFILE,
)


@dataclass(frozen=True)
class TaskResource:
    """A non-secret inventory reference permitted by one investigation."""

    type: str
    id: str
    environment: str
    namespace: str = ""
    kind: str = ""
    name: str = ""

    @classmethod
    def from_payload(cls, payload: Any) -> "TaskResource":
        """Validate one backend-issued resource reference."""
        fields = {"type", "id", "environment", "namespace", "kind", "name"}
        if not isinstance(payload, Mapping) or not {"type", "id", "environment"}.issubset(payload):
            raise ValueError("invalid_task_resource")
        raw_id = payload["id"]
        if isinstance(raw_id, int) and raw_id > 0:
            resource_id = str(raw_id)
        elif isinstance(raw_id, str) and 0 < len(raw_id) <= 512:
            resource_id = raw_id
        else:
            raise ValueError("invalid_task_resource")
        if set(payload) - fields or not all(
            isinstance(value, str) and 0 < len(value) <= 512
            for key, value in payload.items()
            if key != "id"
        ):
            raise ValueError("invalid_task_resource")
        return cls(
            type=payload["type"],
            id=resource_id,
            environment=payload["environment"],
            namespace=payload.get("namespace", ""),
            kind=payload.get("kind", ""),
            name=payload.get("name", ""),
        )

    def as_payload(self) -> dict[str, str]:
        """Return the bounded public fields used in tool arguments."""
        return {
            key: value
            for key, value in {
                "type": self.type,
                "id": self.id,
                "environment": self.environment,
                "namespace": self.namespace,
                "kind": self.kind,
                "name": self.name,
            }.items()
            if value
        }


@dataclass(frozen=True)
class TaskBinding:
    """A backend-issued task capability; secrets never enter durable turn state."""

    investigation_id: str
    attempt_id: str
    credential: str = field(repr=False)
    resource_id: str
    start: str
    end: str
    user_id: str = field(default="", repr=False)
    profile_id: str = ""
    profile_version: str = ""
    resources: tuple[TaskResource, ...] = ()

    @classmethod
    def from_payload(cls, payload: Any) -> TaskBinding:
        """Accept only a complete bounded capability from authenticated intake."""
        fields = {"investigation_id", "attempt_id", "credential", "resource_id", "start", "end"}
        if (
            not isinstance(payload, Mapping)
            or not fields.issubset(payload)
            or set(payload) - fields - {"profile_id", "profile_version", "user_id", "resources"}
        ):
            raise ValueError("invalid_task_binding")
        if not all(
            isinstance(value, str) and 0 < len(value) <= 4096
            for key, value in payload.items()
            if key != "resources"
        ):
            raise ValueError("invalid_task_binding")
        values: dict[str, str] = {
            key: value for key, value in payload.items() if key != "resources"
        }
        if bool(values.get("profile_id")) != bool(values.get("profile_version")):
            raise ValueError("invalid_profile_binding")
        start = datetime.fromisoformat(values["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(values["end"].replace("Z", "+00:00"))
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or not 0 < (end - start).total_seconds() <= 86400
        ):
            raise ValueError("invalid_task_window")
        raw_resources = payload.get("resources", [])
        if not isinstance(raw_resources, list) or len(raw_resources) > 16:
            raise ValueError("invalid_task_resources")
        resources = tuple(TaskResource.from_payload(item) for item in raw_resources)
        if resources and all(resource.id != values["resource_id"] for resource in resources):
            raise ValueError("invalid_task_resource_primary")
        return cls(**values, resources=resources)

    def scope(self) -> dict[str, str]:
        """Nonsecret durable binding used to constrain continuation requests."""
        scope = {
            "investigation_id": self.investigation_id,
            "attempt_id": self.attempt_id,
            "resource_id": self.resource_id,
            "start": self.start,
            "end": self.end,
        }
        if self.profile_id:
            scope.update(profile_id=self.profile_id, profile_version=self.profile_version)
        return scope

    def resource_options(self) -> tuple[dict[str, str], ...]:
        """Return selectable resources, falling back to the legacy primary scope."""
        if self.resources:
            return tuple(resource.as_payload() for resource in self.resources)
        return ({"id": self.resource_id},)


_binding: ContextVar[TaskBinding | None] = ContextVar("hosted_task_binding", default=None)


def readonly_profile_enabled() -> bool:
    """Whether this process is dedicated to platform read-only investigations."""
    return os.getenv(OPS_ADMIN_PROFILE_ENV, "") in {
        OPS_ADMIN_READONLY_PROFILE,
        OPS_ADMIN_INVESTIGATOR_PROFILE,
    }


def current_task_binding() -> TaskBinding | None:
    """Return the capability bound to this turn only."""
    return _binding.get()


@contextmanager
def bound_task_binding(binding: TaskBinding | None) -> Iterator[None]:
    """Scope a capability to one worker turn, including pooled tool providers."""
    token = _binding.set(binding)
    try:
        yield
    finally:
        _binding.reset(token)
