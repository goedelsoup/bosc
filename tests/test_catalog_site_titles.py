"""Regression guard for per-site catalog descriptor titles (#1250).

The bug: every non-Lima site's published catalog feed carried **hardcoded Lima/Allen-County
titles** ("Allen County Economic Baseline", "Lima-Loop Hydrology…") over data that is actually
the sibling site's own (Champaign County, Hancock County, …). This locks the fix in:

- a ``slug-scoped`` entry's title, materialized for a site, names *that site's* county and never
  another site's (``watermark.catalog.sites.site_title``); and
- a freshly exported non-Lima bundle's catalog feed carries none of the Lima literals at all
  (the shared-data entries were re-scoped so they don't leak into a sibling's catalog).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.catalog import load_entries
from watermark.catalog.sites import owner_matches, site_title
from watermark.config import Settings
from watermark.sites import SITES

REPO_ROOT = Path(__file__).resolve().parent.parent
_SETTINGS = Settings(data_dir=REPO_ROOT / "data")

# The Lima/Allen-County literals that must never label a sibling site's own data (AC1).
_LIMA_LITERALS = ("Allen County", "Lima-Loop", "FIPS 39003")

_SLUG_SCOPED = [e for e in load_entries(settings=_SETTINGS) if e.site_scope == "slug-scoped"]
# The other sites' county names — a materialized title must never contain one of these.
_COUNTY_BY_SLUG = {slug: SITES[slug].county_name for slug in SITES}


def test_slug_scoped_titles_are_parameterized() -> None:
    """Every county-labelled slug-scoped entry carries a ``title_template`` — otherwise its fixed
    Lima title would be copied verbatim into every sibling bundle (the #1250 defect)."""
    for entry in _SLUG_SCOPED:
        if "County" in entry.title:
            assert entry.title_template, (
                f"slug-scoped {entry.id!r} has a county in its title but no title_template — "
                "its Lima literal would leak into every sibling site's catalog"
            )


@pytest.mark.parametrize("slug", sorted(SITES))
def test_slug_scoped_title_names_only_its_own_county(slug: str) -> None:
    """A slug-scoped title, resolved for a site, names that site's county and no other site's."""
    own = _COUNTY_BY_SLUG[slug]
    own_county = own.partition(",")[0].strip()  # "Allen County" from "Allen County, OH"
    for entry in _SLUG_SCOPED:
        if not entry.title_template:
            continue
        title = site_title(entry, slug)
        assert own_county in title, (
            f"{entry.id}@{slug} title {title!r} drops its own county {own!r}"
        )
        for other_slug, other_county in _COUNTY_BY_SLUG.items():
            if other_county == own:
                continue  # same county+state (none today) — not a cross-site leak
            assert other_county not in title, (
                f"{entry.id}@{slug} title {title!r} leaks {other_slug}'s county {other_county!r}"
            )


def test_fort_wayne_rsei_reads_indiana_not_ohio() -> None:
    """Fort Wayne is *Allen County, IN* — its RSEI title must not inherit Lima's *OH* (AC3)."""
    rsei = next(e for e in _SLUG_SCOPED if e.id == "rsei-inventory")
    title = site_title(rsei, "fort-wayne")
    assert "Allen County, IN" in title
    assert "Allen County, OH" not in title
    assert "FIPS 39003" not in title


def test_no_lima_literal_leaks_into_a_sibling_catalog() -> None:
    """A freshly exported non-Lima bundle's catalog feed carries no Lima/Allen literal — the
    end-to-end guard over both the parameterized slug-scoped titles and the re-scoped shared
    entries (subdivisions/hydrology) that used to ship into every sibling's catalog."""
    from watermark.site.catalog import export_catalog

    sibling = Settings(data_dir=REPO_ROOT / "data", site="urbana")
    items = export_catalog(sibling)
    assert items, "expected a non-empty catalog feed for urbana"
    for item in items:
        for literal in _LIMA_LITERALS:
            assert literal not in item.title, f"{item.id} title leaks {literal!r}: {item.title!r}"
    # The Allen-County-only registry is Lima's alone — it must not even appear in a sibling feed.
    ids = {item.id for item in items}
    assert "subdivisions" not in ids, "subdivisions is lima-legacy and must not ship to a sibling"
    assert owner_matches("lima-legacy", "urbana") is False  # invariant this rests on
