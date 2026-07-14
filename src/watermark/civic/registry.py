"""Load the committed subdivisions registry into validated models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from watermark.civic.models import Registry
from watermark.config import Settings, get_settings


def registry_path(settings: Settings | None = None) -> Path:
    """Path to the active site's committed registry YAML.

    Per-site under ``data/reference/subdivisions/<site>/subdivisions.yaml``, except
    ``lima`` which keeps the legacy flat ``subdivisions/subdivisions.yaml`` so the
    committed litigation corpus is never relocated — the onboarding convention that
    Lima keeps its flat legacy paths while every peer slug-scopes its outputs.
    """
    settings = settings or get_settings()
    base = settings.reference_dir / "subdivisions"
    if settings.site == "lima":
        return base / "subdivisions.yaml"
    return base / settings.site / "subdivisions.yaml"


def load_registry(settings: Settings | None = None) -> Registry:
    """Parse and validate the active site's subdivisions registry.

    Guards against a cross-site read: the registry's ``meta.site`` must equal the
    active ``settings.site``. A peer registry that resolved under Lima (or Lima's
    that resolved under a peer) is a hard error, never a silent wrong-site load.
    """
    settings = settings or get_settings()
    path = registry_path(settings)
    raw = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    reg = Registry.model_validate(raw)
    declared = reg.meta.get("site")
    if declared != settings.site:
        raise ValueError(
            f"subdivisions registry {path} declares meta.site {declared!r} but the "
            f"active site is {settings.site!r} — refusing a cross-site read. Add "
            f"'site: {settings.site}' to that registry's meta block."
        )
    return reg
