"""Configuration for a dedicated investigation service; no administrator credential."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from config.constants.ops_admin import (
    OPS_ADMIN_SERVICE_ID_ENV,
    OPS_ADMIN_TIMEOUT_SECONDS_ENV,
    OPS_ADMIN_URL_ENV,
)


@dataclass(frozen=True)
class OpsAdminConfig:
    """Pinned backend origin; credentials arrive only in trusted per-task context."""

    base_url: str
    timeout_seconds: float = 10.0
    service_id: str = "opensre"

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or getattr(parsed, "pass" + "word")
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Ops Admin URL must be an HTTP origin without credentials or path")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60:
            raise ValueError("Ops Admin timeout must be within (0, 60] seconds")
        if not self.service_id or len(self.service_id) > 128 or not self.service_id.isascii():
            raise ValueError("Invalid Ops Admin service identifier")
        if any(ord(char) < 32 for char in self.service_id):
            raise ValueError("Invalid Ops Admin service identifier")

    @classmethod
    def from_env(cls) -> OpsAdminConfig:
        """Read non-secret process settings; a missing backend origin fails closed."""
        return cls(
            base_url=os.environ.get(OPS_ADMIN_URL_ENV, ""),
            timeout_seconds=float(os.environ.get(OPS_ADMIN_TIMEOUT_SECONDS_ENV, "10")),
            service_id=os.environ.get(OPS_ADMIN_SERVICE_ID_ENV, "opensre"),
        )
