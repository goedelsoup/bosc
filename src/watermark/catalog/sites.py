"""Site-aware catalog views (epic #631, issue #628).

Makes "which datasets exist / are missing / are stale for site X" a first-class query, instead
of resolving the eight ``SiteProfile`` ``*_relpath`` fields and stat-ing each by hand. The
catalog already carries the per-site axis on every entry (``site_scope``), so a site's expected
dataset set — and the gaps that gate its parity promotion — is *derivable* here rather than
tribal knowledge.

Relevance by ``site_scope``: a ``basin-shared`` dataset is shared by every site; a
``slug-scoped`` dataset is expected per-site (its ``{site}`` template resolves to that site's
copy); a ``lima-legacy`` dataset belongs only to Lima's un-slugged files. **Presence** is
resolved *for the site*: a slug-scoped entry is present for ``findlay`` only if
``…/findlay/…`` exists — which is exactly the onboarding-readiness signal.

The per-site resolution itself lives in :mod:`watermark.catalog.resolve` (#2066), shared with
:mod:`watermark.catalog.reconcile` so a site's *observation* and its *presence* cannot answer
"what is this site's copy" two different ways — which they did: this module required **every**
resolved member to exist, a stricter rule than reconcile's own, so the 21 sites holding their
own ``rsei-inventory`` reported it missing over a ``{site}/enclave.yaml`` only the one
federal-enclave site can have.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from watermark.catalog import CatalogEntry, Scope, SiteScope, load_entries
from watermark.catalog.reconcile import reconcile
from watermark.catalog.resolve import REFERENCE_LAYOUT_SITE, present_for_site, resolved_for_site
from watermark.config import Settings, get_settings
from watermark.sites import SITES, get_profile

# Lima keeps its reference/extracted files un-slugged (the `lima-legacy`/un-templated peer);
# every other site's slug-scoped copy lives under a `<slug>/` segment (the `{site}` template).
# Re-exported under its historical name; the rule itself now lives in `catalog.resolve` (#2066),
# shared with `reconcile` so a site's observation and its presence answer one question once.
_LEGACY_SITE = REFERENCE_LAYOUT_SITE


def owner_matches(site_scope: SiteScope, slug: str) -> bool:
    """Whether a dataset with this ``site_scope`` belongs to ``slug`` (#778) — the single owner
    rule shared by the readiness view and the bundle feed.

    ``basin-shared`` (national) and ``slug-scoped`` (a ``{site}`` template every site instances)
    belong to everyone; ``lima-legacy`` only to the reference build. The explicit-owner kinds
    match the site's identity: ``site:<slug>`` its slug, ``basin:<name>`` its ``basin``,
    ``state:<XX>`` its ``eia_state``. An unknown/unregistered site is treated as no match for the
    owner kinds (it can't claim another site's data).
    """
    if site_scope in ("basin-shared", "slug-scoped"):
        return True
    if site_scope == "lima-legacy":
        return slug == _LEGACY_SITE
    kind, _, value = site_scope.partition(":")
    if kind == "site":
        return slug == value
    if slug not in SITES:
        return False
    profile = get_profile(slug)
    if kind == "basin":
        return profile.basin == value
    if kind == "state":
        return profile.eia_state == value
    return False


def is_relevant(entry: CatalogEntry, slug: str) -> bool:
    """Whether a dataset is part of ``slug``'s expected set (its owner matches the site)."""
    return owner_matches(entry.site_scope, slug)


def site_title(entry: CatalogEntry, slug: str) -> str:
    """The catalog entry's title as materialized for ``slug`` (#1250).

    A ``slug-scoped`` dataset holds the active site's *own* data, so a Lima literal baked into the
    title ("Allen County Economic Baseline") would mislabel every sibling site's bundle. When the
    entry carries a :attr:`~watermark.catalog.CatalogEntry.title_template`, it is resolved against
    ``slug``'s :class:`~watermark.sites.SiteProfile` — ``{county_state}`` ("Allen County, OH"),
    ``{county}`` ("Allen County"), ``{state}``, ``{place}``, ``{fips}`` — so the title names the
    site's own county (and disambiguates Fort Wayne's *Allen County, IN* from Lima's *Allen County,
    OH*). No template, or an unregistered slug, falls back to the fixed :attr:`title` verbatim.
    """
    if not entry.title_template or slug not in SITES:
        return entry.title
    profile = get_profile(slug)
    county_state = profile.county_name  # e.g. "Allen County, OH"
    county, _, state = county_state.partition(",")
    return entry.title_template.format(
        county_state=county_state,
        county=county.strip(),
        state=state.strip() or profile.eia_state,
        place=profile.place,
        fips=profile.rsei_fips,
    )


class SiteDatasetStatus(BaseModel):
    """One catalog dataset's standing *for a given site*."""

    model_config = ConfigDict(extra="forbid")

    id: str
    scope: Scope
    site_scope: SiteScope
    present: bool  # this site's copy is on disk (no declared concrete member absent)
    stale: bool  # past refresh.ttl_days — THIS site's copy, not the network's (#2066)
    # Every location this site's copy may occupy. Usually one; the reference build can carry two
    # for a slug-scoped dataset (its un-slugged peer AND a slugged file), and a site that has no
    # copy is still told where one would go — which is what the onboarding gate needs.
    resolved: list[str] = Field(default_factory=list)


def site_view(
    slug: str, *, settings: Settings | None = None, now: datetime | None = None
) -> list[SiteDatasetStatus]:
    """Every catalog dataset relevant to ``slug``, with per-site presence + freshness."""
    settings = settings or get_settings()
    snapshot = reconcile(settings=settings, now=now)
    out: list[SiteDatasetStatus] = []
    for entry in load_entries(settings=settings):
        if not is_relevant(entry, slug):
            continue
        obs = snapshot.entries.get(entry.id)
        # Freshness for THIS site: a slug-scoped dataset carries its own `asof` per site, so the
        # entry-level flag is the network's oldest copy, not this one's (#2066). Falls back to the
        # entry record for the shared/single-owner scopes, which have no site axis.
        site_obs = obs.sites.get(slug) if obs else None
        out.append(
            SiteDatasetStatus(
                id=entry.id,
                scope=entry.scope,
                site_scope=entry.site_scope,
                present=present_for_site(entry, slug, settings),
                stale=bool(site_obs.stale if site_obs is not None else (obs and obs.stale)),
                resolved=resolved_for_site(entry, slug),
            )
        )
    return sorted(out, key=lambda s: (s.scope, s.id))


class SiteReadiness(BaseModel):
    """A site's dataset-coverage rollup — the parity-promotion readiness signal."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    total: int  # datasets relevant to this site
    present: int  # of those, present on disk for the site
    missing: list[str] = Field(default_factory=list)  # relevant dataset ids absent for the site
    stale: list[str] = Field(default_factory=list)  # present-but-stale dataset ids

    @property
    def ready(self) -> bool:
        """No missing datasets — every expected dataset is present for the site."""
        return not self.missing


def readiness(
    slug: str, *, settings: Settings | None = None, now: datetime | None = None
) -> SiteReadiness:
    """Roll a site's :func:`site_view` into present/missing/stale counts for the review gate."""
    view = site_view(slug, settings=settings, now=now)
    return SiteReadiness(
        slug=slug,
        total=len(view),
        present=sum(1 for s in view if s.present),
        missing=[s.id for s in view if not s.present],
        stale=[s.id for s in view if s.present and s.stale],
    )
