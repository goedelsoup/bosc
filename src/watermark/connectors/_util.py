"""Small shared helpers for the connectors (#601)."""

from __future__ import annotations

from typing import Any, overload


def to_str(value: Any) -> str | None:
    """Coerce ``value`` to a trimmed non-empty ``str``, or ``None``.

    ``None`` and whitespace-only strings both collapse to ``None`` — the connectors'
    shared "empty field means absent" rule for external record values.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@overload
def to_float(value: Any) -> float | None: ...
@overload
def to_float(value: Any, default: float) -> float: ...
def to_float(value: Any, default: float | None = None) -> float | None:
    """Parse ``value`` to ``float``; return ``default`` (``None`` unless given) on a
    ``TypeError``/``ValueError``. The one home for the connectors' numeric coercion —
    callers that want a non-optional float pass an explicit ``default``."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any) -> int | None:
    """Parse ``value`` to ``int`` (via ``float`` so ``"5.0"`` works), or ``None``.

    For external count/identifier fields already carried as whole numbers; truncation
    matches the source (never a rounded quantity — that is the caller's concern).
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
