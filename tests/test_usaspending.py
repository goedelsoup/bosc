"""Tests for the USASpending federal-award resolution (`watermark usaspending`)."""

from __future__ import annotations

import json
from pathlib import Path

from watermark import usaspending
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_profile(settings: Settings, recipient_id: str, payload: dict) -> None:
    """Write a cached recipient-profile response (year=all)."""
    key = f"GET /recipient/{recipient_id}/?year=all "
    p = usaspending._cache_path(settings, key.strip())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_recipient_verifies_uei(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", usaspending_offline=True)
    rid = "abc-C"
    _seed_profile(
        settings,
        rid,
        {
            "name": "ACME DEFENSE INC.",
            "uei": "ACMEUEI00001",
            "duns": "123456789",
            "recipient_level": "C",
            "total_transaction_amount": 1234567.0,
            "parent_name": "ACME HOLDINGS",
            "parent_uei": "ACMEUEI99999",
        },
    )
    out = usaspending.resolve_recipient(
        "Acme Defense Inc.", rid, "ACMEUEI00001", lei="LEI0001", nexus="verified", settings=settings
    )
    assert isinstance(out, usaspending.RecipientAward)
    assert out.uei == "ACMEUEI00001"
    assert out.total_obligations == 1234567.0
    assert out.lei == "LEI0001"
    assert out.parent_name == "ACME HOLDINGS"
    assert out.nexus == "verified"


def test_uei_mismatch_becomes_lead(tmp_path: Path) -> None:
    """A profile whose UEI != the pinned UEI drops to a lead, never a wrong attribution."""
    settings = Settings(data_dir=tmp_path / "data", usaspending_offline=True)
    rid = "wrong-C"
    _seed_profile(settings, rid, {"name": "SOMEONE ELSE", "uei": "OTHERUEI0001"})
    out = usaspending.resolve_recipient("Acme Defense Inc.", rid, "ACMEUEI00001", settings=settings)
    assert isinstance(out, usaspending.AwardLead)
    assert "mismatch" in (out.note or "")


def test_committed_inventory_loads_and_is_clean() -> None:
    """The committed awards.yaml parses and the pinned nexus discipline holds."""
    inv = usaspending.load_inventory(Settings(data_dir=REPO_ROOT / "data").reference_dir)
    assert inv is not None
    assert inv.records, "expected committed federal-award records"
    by_name = {r.watchlist_name: r for r in inv.records}
    # The corridor's federal defense nexus dwarfs the corridor land recipient.
    gdls = by_name["General Dynamics Land Systems Inc."]
    amazon = by_name["Amazon.com Services LLC"]
    assert gdls.nexus == "verified" and gdls.total_obligations > 1e10
    assert amazon.nexus == "verified" and amazon.total_obligations < 1e7
    # Amazon corridor recipient is the warehouse entity, not AWS.
    assert amazon.uei == "TMKBFBRHFKH3"
    # Google is present but tagged open (Scioto Dazzler, not the Lima campus).
    assert by_name["Google LLC"].nexus == "open"


def test_offline_without_cache_raises(tmp_path: Path) -> None:
    import pytest

    settings = Settings(data_dir=tmp_path / "data", usaspending_offline=True)
    with pytest.raises(usaspending.UsaSpendingOfflineError):
        usaspending.resolve_recipient("X", "missing-C", "UEI", settings=settings)
