"""Tests for the GLEIF LEI resolution (`watermark lei`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark import gleif
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_cache(settings: Settings, lei: str) -> None:
    """Write cached GLEIF responses for one LEI (record + 404 parents)."""

    def write(path: str, payload: dict) -> None:
        p = gleif._cache_path(settings, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")

    write(
        f"/lei-records/{lei}",
        {
            "data": {
                "attributes": {
                    "lei": lei,
                    "entity": {
                        "legalName": {"name": "ACME DEFENSE CORPORATION"},
                        "jurisdiction": "US-DE",
                        "status": "ACTIVE",
                        "legalAddress": {"city": "Wilmington", "region": "US-DE", "country": "US"},
                    },
                    "registration": {"status": "ISSUED", "lastUpdateDate": "2025-01-01"},
                }
            }
        },
    )
    # Direct parent present, ultimate parent absent (404).
    write(
        f"/lei-records/{lei}/direct-parent",
        {
            "data": {
                "attributes": {
                    "lei": "PARENTLEI0000000000XX",
                    "entity": {"legalName": {"name": "ACME HOLDINGS"}},
                }
            }
        },
    )
    write(f"/lei-records/{lei}/ultimate-parent", {"_status": 404})


def test_fetch_record_offline(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", gleif_offline=True)
    lei = "ACME0000000000000001"
    _seed_cache(settings, lei)

    rec = gleif.fetch_record(lei, watchlist_name="Acme", note="test", settings=settings)
    assert rec is not None
    assert rec.lei == lei
    assert rec.legal_name == "ACME DEFENSE CORPORATION"
    assert rec.jurisdiction == "US-DE"
    assert rec.entity_status == "ACTIVE"
    assert rec.registration_status == "ISSUED"
    assert rec.legal_address is not None and rec.legal_address.city == "Wilmington"
    # Direct parent parsed; ultimate parent 404 -> None.
    assert rec.direct_parent is not None and rec.direct_parent.name == "ACME HOLDINGS"
    assert rec.ultimate_parent is None


def test_offline_uncached_raises(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", gleif_offline=True)
    with pytest.raises(gleif.GleifOfflineError):
        gleif.fetch_record("NOTCACHED00000000001", watchlist_name="x", settings=settings)


def test_committed_inventory_loads() -> None:
    """The committed corridor LEI inventory loads with the expected shape."""
    inv = gleif.load_inventory(Settings().reference_dir)
    assert inv is not None, "data/reference/gleif/lei-records.yaml is missing"
    assert len(inv.records) >= 5
    # Every record carries a 20-char LEI.
    assert all(len(r.lei) == 20 for r in inv.records)
    # GDLS resolves and reports General Dynamics Corporation as its ultimate parent.
    gdls = next((r for r in inv.records if "LAND SYSTEMS" in r.legal_name.upper()), None)
    assert gdls is not None
    assert gdls.ultimate_parent is not None
    assert "GENERAL DYNAMICS" in gdls.ultimate_parent.name.upper()
