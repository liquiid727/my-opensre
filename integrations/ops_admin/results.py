"""Defense-in-depth result redaction before model input and transcript capture."""

from __future__ import annotations

from infrastructure.safety.secret_redaction import redact_text


def sanitized_result(value: object, credential: str) -> object:
    """Drop secret fields and redact credential patterns and the current task secret."""
    if isinstance(value, dict):
        return {
            str(sanitized_result(str(key), credential)): (
                "[REDACTED]"
                if any(word in str(key).lower() for word in ("token", "password", "secret", "credential", "authorization", "kubeconfig"))
                else sanitized_result(item, credential)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitized_result(item, credential) for item in value]
    if isinstance(value, str):
        return redact_text(value.replace(credential, "[REDACTED]")) if credential else redact_text(value)
    return value
