"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = REPO_ROOT / "data" / "extracted"


@pytest.fixture
def summary_path() -> Path:
    """Path to the committed roundabouts summary extraction."""
    return EXTRACTED / "aedg" / "roundabouts.summary.opc.yaml"
