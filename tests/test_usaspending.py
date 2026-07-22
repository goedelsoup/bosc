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
    # The stretch breakdown (#1662) is resolved and internally consistent: the JSMC operator's
    # federal spend is overwhelmingly defense, and its annual flow + category mix are populated.
    assert gdls.annual_obligations, "expected an annual flow on the committed GDLS record"
    assert gdls.by_psc and gdls.by_naics, "expected PSC + NAICS category mixes"
    assert gdls.defense_share is not None and gdls.defense_share > 0.9
    assert gdls.defense_obligations and gdls.civilian_obligations is not None
    # Google's federal footprint is civilian — the split must not read it as defense.
    assert (by_name["Google LLC"].defense_share or 0.0) < 0.5


def test_offline_without_cache_raises(tmp_path: Path) -> None:
    import pytest

    settings = Settings(data_dir=tmp_path / "data", usaspending_offline=True)
    with pytest.raises(usaspending.UsaSpendingOfflineError):
        usaspending.resolve_recipient("X", "missing-C", "UEI", settings=settings)


def test_resolve_recipient_breakdown(monkeypatch) -> None:
    """The breakdown resolves the annual flow, PSC/NAICS mix, and defense-vs-civilian split.

    ``_request`` is stubbed so the test is hermetic (no cache seeding, no network); the classifier
    must sum the DoD toptier as defense and everything else as civilian.
    """

    def fake_request(method: str, path: str, body, *, settings) -> dict:
        if path.endswith("?year=all"):
            return {"uei": "ACMEUEI00001", "name": "ACME DEFENSE INC.", "recipient_level": "C"}
        if path.startswith("/recipient/"):  # a year-scoped profile
            fy = path.split("year=")[-1]
            return {"total_transaction_amount": 100.0 * int(fy)}
        if path.endswith("/psc/"):
            return {"results": [{"code": "2350", "name": "TANKS", "amount": 900.0}]}
        if path.endswith("/naics/"):
            return {"results": [{"code": "336992", "name": "ARMOR MFG", "amount": 800.0}]}
        if path.endswith("/awarding_agency/"):
            return {
                "results": [
                    {"name": "Department of Defense", "amount": 900.0},
                    {"name": "General Services Administration", "amount": 100.0},
                ]
            }
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(usaspending, "_request", fake_request)
    settings = Settings(usaspending_offline=True)
    out = usaspending.resolve_recipient(
        "Acme Defense Inc.",
        "abc-C",
        "ACMEUEI00001",
        nexus="verified",
        breakdown=True,
        annual_years=[2023, 2024],
        settings=settings,
    )
    assert isinstance(out, usaspending.RecipientAward)
    assert out.breakdown_window == "2007-10-01..2024-09-30"
    assert [(a.fiscal_year, a.obligations) for a in out.annual_obligations] == [
        (2023, 202300.0),
        (2024, 202400.0),
    ]
    assert out.by_psc[0].code == "2350" and out.by_naics[0].code == "336992"
    assert out.defense_obligations == 900.0 and out.civilian_obligations == 100.0
    assert out.defense_share == 0.9


def test_watchlist_is_per_site(tmp_path: Path, monkeypatch) -> None:
    """A site with no committed watchlist resolves to an empty inventory, never Lima's (#1662)."""
    settings = Settings(data_dir=tmp_path / "data", site="fort-wayne", usaspending_offline=True)
    # No watchlist file exists under entities/fort-wayne/profiles/ — resolution must not fetch.
    monkeypatch.setattr(
        usaspending,
        "_request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    inv = usaspending.resolve_watchlist(settings)
    assert inv.records == [] and inv.meta["site"] == "fort-wayne"


def test_awards_dir_is_slug_scoped(tmp_path: Path) -> None:
    """Lima keeps the flat awards path; a peer is slug-scoped (#1662)."""
    ref = tmp_path / "reference"
    assert usaspending.awards_dir(ref, "lima") == ref / "usaspending"
    assert usaspending.awards_dir(ref, "fort-wayne") == ref / "usaspending" / "fort-wayne"
