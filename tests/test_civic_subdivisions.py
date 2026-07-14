"""Civic subdivisions: registry load, platform classification, offline discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.civic import load_registry
from watermark.civic.discovery import (
    classify_platform,
    discover,
    find_records_links,
)
from watermark.civic.models import Platform
from watermark.civic.registry import registry_path
from watermark.config import Settings
from watermark.connectors import OfflineError


def test_registry_loads_and_validates(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    # All 12 townships present.
    townships = [s for s in reg.subdivisions if s.type == "township"]
    assert len(townships) == 12
    # Grounded cadence is carried verbatim.
    shawnee = reg.get("shawnee-township")
    assert shawnee is not None
    assert shawnee.meeting_schedule == "2nd & 4th Monday, 7:00 PM"
    assert shawnee.grounded_from == "township-trustees-fiscal-officers"


def test_registry_discovered_corridor_bodies(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    lima = reg.get("lima")
    assert lima is not None
    assert lima.publishing.platform is Platform.CIVICPLUS
    assert lima.publishing.records_url == "https://www.limaohio.gov/AgendaCenter"
    assert lima.publishing.discovered is not None


def test_registry_request_only_body_has_no_url(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    jackson = reg.get("jackson-township")  # no official site found
    assert jackson is not None
    assert jackson.publishing.platform is Platform.REQUEST_ONLY
    assert jackson.publishing.website is None
    assert jackson.publishing.records_url is None
    # "Looked, found nothing online" is still a recorded finding, not a blank.
    assert jackson.publishing.discovered is not None


def _write_registry(path: Path, *, site: object) -> None:
    """Write a minimal valid registry declaring ``meta.site`` (omit if ``site`` is None)."""
    site_line = f"  site: {site}\n" if site is not None else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "meta:\n"
        f"{site_line}"
        "  subject: test registry\n"
        "subdivisions:\n"
        "  - slug: test-body\n"
        "    name: Test Body\n"
        "    type: city\n",
        encoding="utf-8",
    )


def test_registry_path_lima_keeps_flat_legacy_file(tmp_path: Path) -> None:
    # Lima falls back to the flat file — the litigation corpus is never relocated.
    settings = Settings(data_dir=tmp_path, site="lima")
    assert registry_path(settings) == tmp_path / "reference" / "subdivisions" / "subdivisions.yaml"


def test_registry_path_peer_is_slug_scoped(tmp_path: Path) -> None:
    # Every non-Lima site nests its registry under its own slug.
    settings = Settings(data_dir=tmp_path, site="findlay")
    assert (
        registry_path(settings)
        == tmp_path / "reference" / "subdivisions" / "findlay" / "subdivisions.yaml"
    )


def test_load_registry_lima_declares_its_site(civic_settings: Settings) -> None:
    # The committed Lima registry now carries meta.site: lima and still loads.
    reg = load_registry(civic_settings)
    assert reg.meta.get("site") == "lima"


def test_load_registry_peer_reads_peer_not_lima(tmp_path: Path) -> None:
    # A stub peer registry is read for --site <peer>, never Lima's.
    settings = Settings(data_dir=tmp_path, site="findlay")
    _write_registry(registry_path(settings), site="findlay")
    reg = load_registry(settings)
    assert reg.meta.get("site") == "findlay"
    assert [s.slug for s in reg.subdivisions] == ["test-body"]


def test_load_registry_rejects_cross_site_meta(tmp_path: Path) -> None:
    # A registry whose meta.site disagrees with the active site is a hard error.
    settings = Settings(data_dir=tmp_path, site="findlay")
    _write_registry(registry_path(settings), site="lima")  # wrong owner
    with pytest.raises(ValueError, match=r"meta\.site"):
        load_registry(settings)


def test_load_registry_requires_meta_site(tmp_path: Path) -> None:
    # A registry that omits meta.site entirely is rejected, not silently accepted.
    settings = Settings(data_dir=tmp_path, site="findlay")
    _write_registry(registry_path(settings), site=None)
    with pytest.raises(ValueError, match=r"meta\.site"):
        load_registry(settings)


def test_classify_platform_specific_beats_generic() -> None:
    # CivicPlus signal wins even if generic CMS strings are present.
    plat, signals = classify_platform(
        "<html>civicplus agenda center wp-content</html>", final_url="https://oh-lima.civicplus.com"
    )
    assert plat is Platform.CIVICPLUS
    assert "civicplus" in signals

    assert classify_platform("<html>wp-content wp-json</html>")[0] is Platform.WORDPRESS
    assert classify_platform("<html>proudly created with wix.com</html>")[0] is Platform.WIX
    assert classify_platform("<a href='legistar.com'>x</a>")[0] is Platform.GRANICUS


def test_classify_platform_unknown_is_not_guessed() -> None:
    plat, signals = classify_platform("<html><body>plain html</body></html>")
    assert plat is Platform.UNKNOWN
    assert signals == []


def test_find_records_links_resolves_and_dedupes() -> None:
    html = (
        "<a href='/about'>About us</a>"
        "<a href='/minutes/2026'>2026 Minutes</a>"
        "<a href='/x'>Board Agenda</a>"  # matched via link text
        "<a href='/minutes/2026'>dup</a>"  # de-duplicated
    )
    links = find_records_links(html, base_url="https://twp.example/")
    assert links == [
        "https://twp.example/minutes/2026",
        "https://twp.example/x",
    ]


def test_discover_offline_replay(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    shawnee = reg.get("shawnee-township")
    assert shawnee is not None
    result = discover(shawnee, url="https://example-township.test/", settings=civic_settings)
    assert result.platform is Platform.WORDPRESS
    assert result.records_url == "https://example-township.test/meeting-minutes/"
    assert "https://example-township.test/agendas" in result.records_url_candidates


def test_discover_no_homepage_is_flagged(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    jackson = reg.get("jackson-township")  # request_only, no website on record
    assert jackson is not None
    result = discover(jackson, settings=civic_settings)
    assert result.homepage is None
    assert result.platform is Platform.UNKNOWN
    assert result.note is not None


def test_discover_blocked_is_flagged_not_raised(
    civic_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    from watermark.civic import discovery

    def _blocked(url: str, *, settings: Settings) -> dict[str, object]:
        req = httpx.Request("GET", url)
        resp = httpx.Response(403, request=req)
        raise httpx.HTTPStatusError("blocked", request=req, response=resp)

    monkeypatch.setattr(discovery, "_fetch_page", _blocked)
    reg = load_registry(civic_settings)
    bath = reg.get("bath-township")
    assert bath is not None
    result = discover(bath, url="https://waf.example/", settings=civic_settings)
    assert result.platform is Platform.UNKNOWN
    assert result.note is not None and "403" in result.note


def test_discover_offline_miss_raises(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    bath = reg.get("bath-township")
    assert bath is not None
    # A homepage with no recorded cache/fixture -> offline miss is actionable.
    # (Use an .invalid host so a real local cache pull can never mask this.)
    with pytest.raises(OfflineError):
        discover(bath, url="https://bath-township.invalid/", settings=civic_settings)
