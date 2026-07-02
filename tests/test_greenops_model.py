"""GreenOps scaffold (#1077): the report model round-trips, the placeholder is fully
modeled, and the core discipline (nothing metered) is enforced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.greenops import GreenopsReport, placeholder_report
from watermark.greenops.footprint import load_footprint, write_footprint

REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "greenops" / "footprint.placeholder.yaml"


def test_placeholder_report_round_trips(tmp_path: Path) -> None:
    report = placeholder_report()
    out = write_footprint(report, tmp_path / "footprint.yaml")
    assert load_footprint(out) == report


def test_committed_placeholder_fixture_validates() -> None:
    report = load_footprint(PLACEHOLDER_FIXTURE)
    assert report == placeholder_report()  # the fixture is the placeholder, on disk


def test_every_placeholder_figure_is_a_modeled_assumption() -> None:
    report = load_footprint(PLACEHOLDER_FIXTURE)
    values = report.all_values()
    assert values, "the report must expose its provenanced figures"
    # An un-wired source degrades to a stated assumption — never a metered/verified fact.
    assert all(v.source == "assumption" for v in values)
    assert not any(v.verified for v in values)


def test_assert_no_verified_rejects_a_metered_figure() -> None:
    report = load_footprint(PLACEHOLDER_FIXTURE)
    report.assert_no_verified()  # the placeholder passes
    # Slip a connector-"verified" figure in and the discipline guard must catch it.
    report.headline[0].value.source = "connector"
    with pytest.raises(ValueError, match="modeled, not metered"):
        report.assert_no_verified()


def test_report_is_extra_forbid() -> None:
    with pytest.raises(ValueError):
        GreenopsReport.model_validate({**placeholder_report().model_dump(), "surprise": 1})


def test_settings_expose_greenops_knobs_with_safe_defaults() -> None:
    s = Settings()
    # Offline-first defaults: no network, no key required to import/construct.
    assert s.greenops_offline is False
    assert s.greenops_cache_dir == s.cache_dir / "greenops"
    assert s.greenops_fixtures_dir is None
    assert s.greenops_cache_ttl_hours > 0
    # Absent credentials => empty, not a crash (graceful skip is a later-issue concern).
    assert s.anthropic_admin_key == ""
    assert s.aws_access_key_id == "" and s.aws_secret_access_key == ""
    assert s.aws_region == "us-east-1"
