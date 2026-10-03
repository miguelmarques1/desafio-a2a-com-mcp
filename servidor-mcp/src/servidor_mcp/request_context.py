"""Per-request client-capability accessors (consumed by F05)."""

from __future__ import annotations

from typing import Any


def client_capabilities(ctx: Any) -> Any:
    """Capabilities the SDK built from the current request's envelope, or None."""
    return ctx.client_capabilities


def declares_form_elicitation(ctx: Any) -> bool:
    """True only when ``elicitation.form`` is present in this request's capabilities."""
    caps = client_capabilities(ctx)
    if caps is None:
        return False
    elicitation = getattr(caps, "elicitation", None)
    return elicitation is not None and getattr(elicitation, "form", None) is not None
