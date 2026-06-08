"""Load the committed subdivisions registry into validated models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from bosc.civic.models import Registry
from bosc.config import Settings, get_settings


def registry_path(settings: Settings | None = None) -> Path:
    """Path to the committed registry YAML under ``data/reference/subdivisions/``."""
    settings = settings or get_settings()
    return settings.reference_dir / "subdivisions" / "subdivisions.yaml"


def load_registry(settings: Settings | None = None) -> Registry:
    """Parse and validate the subdivisions registry."""
    path = registry_path(settings)
    raw = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    return Registry.model_validate(raw)
