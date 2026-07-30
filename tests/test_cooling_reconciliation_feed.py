"""Tests for the ``cooling-reconciliation`` feed (#1805, epic #1803 P2).

The loader tests are pure reads over the committed reference artifact — they pin the
site-own-rows filter, the Intel positive-control exclusion (the acceptance's hard rule:
a calibration vector never ships as site data, even on a ``new-albany`` bundle), the
self-skip for a site outside the cohort, and the discipline caveats' reconciliation with
the artifact's own meta prose (the distillation can't drift from the canonical text).
Integration tests read the shared Urbana bundle and assert the shipped feed is
byte-consistent with the committed reference YAML — the issue's acceptance.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from watermark.config import Settings
from watermark.hydrology.cooling_reconcile import RECONCILIATION_RELPATH
from watermark.site.cooling_reconciliation import (
    DISCIPLINE_CAVEATS,
    load_cooling_reconciliation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "1.46.0"


def _settings(site: str, data_dir: Path | None = None) -> Settings:
    return Settings(data_dir=data_dir or (REPO_ROOT / "data"), site=site)


def _artifact() -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        yaml.safe_load((REPO_ROOT / "data" / RECONCILIATION_RELPATH).read_text(encoding="utf-8")),
    )


# --- the site-own-rows filter --------------------------------------------------------------
def test_a_cohort_site_ships_its_own_rows_verbatim() -> None:
    feed = load_cooling_reconciliation(_settings("urbana"))
    assert feed is not None
    assert feed.site == "urbana"
    assert [r.site for r in feed.candidates] == ["urbana"]
    # Verbatim: the shipped row round-trips to the artifact's own row (byte-consistency).
    committed = [
        r for r in _artifact()["candidates"] if r["site"] == "urbana" and not r["is_control"]
    ]
    shipped = [r.model_dump(mode="json") for r in feed.candidates]
    assert shipped == committed


def test_a_site_outside_the_cohort_self_skips() -> None:
    # Lima is not a closed-loop candidate — no feed, never an empty shell (#1364).
    assert load_cooling_reconciliation(_settings("lima")) is None


def test_the_intel_control_never_ships_even_on_its_own_site() -> None:
    # The control row is sited `new-albany`, and new-albany IS a registered bundle — the
    # site filter alone would ship the calibration vector as site data. The explicit
    # `is_control` exclusion is what the acceptance pins.
    assert load_cooling_reconciliation(_settings("new-albany")) is None
    control_rows = [r for r in _artifact()["candidates"] if r["is_control"]]
    assert len(control_rows) == 1  # the exclusion is exercised, not vacuous
    assert control_rows[0]["site"] == "new-albany"


def test_missing_artifact_is_a_clean_skip(tmp_path: Path) -> None:
    assert load_cooling_reconciliation(_settings("urbana", data_dir=tmp_path)) is None


# --- the discipline travels as data --------------------------------------------------------
def test_caveats_are_carried_and_pinned_to_the_meta_discipline() -> None:
    """Each carried caveat distills a rule the artifact's meta prose actually states — the
    renderer-facing text can't drift from the canonical discipline block.

    Pairwise, not pooled: each pin phrase must appear in BOTH its own caveat and the meta
    prose, so a caveat reworded away from its rule (or a caveat/rule mismatch hiding behind
    another entry's phrase) fails, not just a wholesale deletion.
    """
    feed = load_cooling_reconciliation(_settings("urbana"))
    assert feed is not None
    assert list(feed.caveats) == list(DISCIPLINE_CAVEATS)
    discipline = str(_artifact()["meta"]["discipline"]).lower()
    # One canonical rule phrase per caveat, in DISCIPLINE_CAVEATS order.
    pins = [
        "never mutates",
        "[inference] bracket, never a headline scalar",
        "never read as 'confirmed dry'",
        "is not a discharge/withdrawal instrument",
        "cannot upgrade the",
        "never the sole basis for a re-archetype",
    ]
    for caveat, phrase in zip(DISCIPLINE_CAVEATS, pins, strict=True):
        assert phrase in caveat.lower(), f"caveat lost its rule phrase {phrase!r}: {caveat!r}"
        assert phrase in discipline, f"discipline rule {phrase!r} not in the artifact meta"


def test_provenance_names_the_artifact_and_its_regen_command() -> None:
    feed = load_cooling_reconciliation(_settings("van-wert"))
    assert feed is not None
    assert RECONCILIATION_RELPATH in feed.source
    assert "cooling-reconcile --write" in feed.source
    assert feed.asof  # the reconciliation's own date rides along


# --- integration: the shared Urbana bundle -------------------------------------------------
# `site_bundle` is conftest's session-wide, cross-worker export factory (#1773) — this module
# reads one feed off the shared Urbana export, so it must never pay for one of its own.
def test_urbana_bundle_ships_the_feed_byte_consistent(
    site_bundle: Callable[[str], Path],
) -> None:
    bundle = site_bundle("urbana")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    ref = next(f for f in manifest["feeds"] if f["name"] == "cooling-reconciliation")
    assert ref["kind"] == "object"
    assert ref["count"] == 1
    payload = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))

    # The acceptance: the shipped outcome equals the committed reference YAML's own row.
    committed = [
        r for r in _artifact()["candidates"] if r["site"] == "urbana" and not r["is_control"]
    ]
    assert payload["candidates"] == committed
    row = payload["candidates"][0]
    assert row["outcome"] == "gap"
    assert row["claim_source"] == "reference"
    assert row["account"]["predicted_makeup"]["value"] == 0.0
    assert not row["is_control"]
    assert payload["caveats"] == list(DISCIPLINE_CAVEATS)


def test_lima_bundle_does_not_carry_the_feed(lima_bundle: Path) -> None:
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert all(f["name"] != "cooling-reconciliation" for f in manifest["feeds"])
