"""Load the committed subdivisions registry into validated models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from watermark.civic.models import Registry
from watermark.config import Settings, get_settings
from watermark.sites import is_reference_site


def registry_path(settings: Settings | None = None) -> Path:
    """Path to the active site's committed registry YAML.

    Per-site under ``data/reference/subdivisions/<site>/subdivisions.yaml``, except
    the reference build (Lima), which keeps the legacy flat
    ``subdivisions/subdivisions.yaml`` so the committed litigation corpus is never
    relocated. Which site owns the flat committed layout is not hardcoded here — it
    comes from ``watermark.sites.is_reference_site`` (the same predicate that gates
    Lima's other flat legacy paths); every peer slug-scopes its outputs.
    """
    settings = settings or get_settings()
    base = settings.reference_dir / "subdivisions"
    if is_reference_site(settings.site):
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
