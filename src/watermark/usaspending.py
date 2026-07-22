"""USASpending federal-award resolution — "who benefits from federal dollars".

Resolves a **per-site** pinned recipient watchlist (Lima keeps the flat
``data/entities/profiles/usaspending-watchlist.yaml``; a sibling site reads its own
``data/entities/<slug>/profiles/usaspending-watchlist.yaml`` — #1662, ME-C) against the
public USASpending.gov API and commits the result to
``data/reference/usaspending/[<slug>/]awards.yaml`` (regenerate with
``watermark [--site <slug>] usaspending``).

Discipline mirrors :mod:`watermark.gleif`: each recipient is pinned by its USASpending
``recipient_id`` **and** ``uei``; resolution fetches the recipient profile by id and
**asserts the returned UEI equals the pinned one** — never a fuzzy name match — so the
committed artifact is litigation-clean. The headline total is **all-time prime-award
obligations** (``?year=all``, the API's ``total_transaction_amount``), recorded verbatim.
Beyond that scalar, an optional breakdown (``settings.usaspending_breakdown``) resolves the
**annual flow** (per-fiscal-year totals), the top **PSC/NAICS category** mix, and a
**defense-vs-civilian** split by awarding agency — so the layer is usable for real economic
work, not just a headline (#1662, ME-C stretch). Each record keeps a ``nexus`` tag
(verified / context / open) so the federal layer never overclaims a corridor connection.

Raw API responses cache under the git-ignored ``data/cache/usaspending/``; only the
small curated YAML is committed.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.sites import site_scoped_path

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

_SOURCE = "USASpending.gov API (api.usaspending.gov), U.S. Treasury; public domain"
_WATCHLIST_REL = ("profiles", "usaspending-watchlist.yaml")
# The reference build (Lima) keeps the flat committed layout; `site_scoped_path` slug-scopes peers.
_REFERENCE_SITE = "lima"
# USASpending's transaction data begins in federal FY2008 (starts 2007-10-01); the breakdown
# searches span from there through the resolution date.
_EPOCH_START = "2007-10-01"
# Awarding-agency toptier names that count as the defense side of the split. The DoD toptier
# aggregates its sub-agencies (Army/Navy/Air Force/DLA/…); the military-department names are kept
# for the rare award booked at that toptier. Everything else is civilian — conservative by design.
_DEFENSE_AGENCIES = frozenset(
    {
        "Department of Defense",
        "Department of the Army",
        "Department of the Navy",
        "Department of the Air Force",
    }
)


class UsaSpendingOfflineError(RuntimeError):
    """Raised when offline mode needs an uncached USASpending response."""


# --- Models ----------------------------------------------------------------
class AnnualObligation(BaseModel):
    """One federal fiscal year's prime-award obligations for a recipient (annual flow)."""

    fiscal_year: int
    obligations: float  # prime-award transaction amount booked that FY (USD)


class CategoryShare(BaseModel):
    """One PSC/NAICS category's share of a recipient's all-time prime-award obligations."""

    code: str
    name: str
    obligations: float


class RecipientAward(BaseModel):
    """One resolved recipient's federal prime-award obligations + optional breakdown."""

    watchlist_name: str
    recipient_id: str
    uei: str
    recipient_name: str
    lei: str | None = None  # GLEIF LEI, when the recipient is also LEI-pinned (cross-ref)
    duns: str | None = None
    recipient_level: str | None = None  # P (parent) | C (child) | R (neither)
    total_obligations: float  # all-time prime-award transaction amount (USD)
    award_window: str = "all-time (year=all)"
    parent_name: str | None = None
    parent_uei: str | None = None
    nexus: str = "context"  # verified | context | open — how it ties to the corridor
    note: str | None = None
    # Optional breakdown (settings.usaspending_breakdown; #1662, ME-C stretch). Empty when the
    # breakdown is off — the record still carries its verbatim all-time total.
    breakdown_window: str | None = None  # the "<start>..<end>" span the breakdown searches covered
    annual_obligations: list[AnnualObligation] = []  # trailing per-FY flow, oldest → newest
    by_psc: list[CategoryShare] = []  # top Product/Service-Code categories by obligation
    by_naics: list[CategoryShare] = []  # top NAICS industry categories by obligation
    defense_obligations: float | None = None  # obligations booked by DoD-family awarding agencies
    civilian_obligations: float | None = None  # obligations booked by all other awarding agencies
    defense_share: float | None = None  # defense / (defense + civilian), 0..1; None if unresolved


class AwardLead(BaseModel):
    """A watchlist recipient that did not resolve (id missing or UEI mismatch)."""

    name: str
    recipient_id: str | None = None
    uei: str | None = None
    note: str | None = None


class UsaSpendingInventory(BaseModel):
    """The committed USASpending resolution: provenance meta + records + leads."""

    meta: dict[str, Any]
    records: list[RecipientAward]
    leads: list[AwardLead] = []


# --- HTTP + cache ----------------------------------------------------------
def _cache_path(settings: Settings, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return settings.usaspending_cache_dir / f"{digest}.json"


def _request(method: str, path: str, body: dict[str, Any] | None, *, settings: Settings) -> Any:
    """Issue a cached GET/POST against the USASpending API; returns parsed JSON."""
    key = f"{method} {path} {json.dumps(body, sort_keys=True) if body else ''}".strip()
    cache = _cache_path(settings, key)
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    if settings.usaspending_offline:
        raise UsaSpendingOfflineError(
            f"offline: no cached USASpending response for {key} ({cache})"
        )

    import httpx

    url = f"{settings.usaspending_base_url}{path}"
    log.info("usaspending.fetch", method=method, path=path)
    timeout = settings.usaspending_request_timeout_s
    if method == "POST":
        resp = httpx.post(url, json=body, timeout=timeout, follow_redirects=True)
    else:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    payload = resp.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _profile(recipient_id: str, *, year: str = "all", settings: Settings) -> dict[str, Any]:
    """The recipient profile for a pinned recipient_id, scoped to ``year`` (``all`` or an FY)."""
    data = _request("GET", f"/recipient/{recipient_id}/?year={year}", None, settings=settings)
    return data if isinstance(data, dict) else {}


def _category(
    recipient_id: str,
    category: str,
    window: tuple[str, str],
    *,
    settings: Settings,
    limit: int,
) -> list[dict[str, Any]]:
    """One ``spending_by_category`` slice (psc / naics / awarding_agency) for a recipient."""
    body = {
        "category": category,
        "filters": {
            "recipient_id": recipient_id,
            "time_period": [{"start_date": window[0], "end_date": window[1]}],
        },
        "limit": limit,
    }
    data = _request("POST", f"/search/spending_by_category/{category}/", body, settings=settings)
    results = data.get("results") if isinstance(data, dict) else None
    return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []


def _current_fiscal_year(today: _dt.date) -> int:
    """The federal fiscal year of ``today`` (FY N runs Oct 1 N-1 → Sep 30 N)."""
    return today.year + 1 if today.month >= 10 else today.year


def _fiscal_window(annual_years: list[int]) -> tuple[str, str]:
    """The ``(start, end)`` search window covering ``annual_years`` back to the USASpending epoch."""
    end_fy = max(annual_years) if annual_years else _current_fiscal_year(_dt.date.today())
    return (_EPOCH_START, f"{end_fy}-09-30")


def _resolve_breakdown(
    recipient_id: str, *, annual_years: list[int], settings: Settings
) -> dict[str, Any]:
    """Resolve the annual flow + PSC/NAICS mix + defense/civilian split for one recipient.

    Every figure is verbatim from USASpending: per-FY totals from the year-scoped profile, the
    category mixes from ``spending_by_category``, and the defense/civilian split by summing the
    awarding-agency category against :data:`_DEFENSE_AGENCIES`. All obligations are prime-award
    ``total_transaction_amount``, consistent with the headline scalar.
    """
    window = _fiscal_window(annual_years)
    annual = [
        AnnualObligation(
            fiscal_year=fy,
            obligations=float(
                _profile(recipient_id, year=str(fy), settings=settings).get(
                    "total_transaction_amount"
                )
                or 0.0
            ),
        )
        for fy in annual_years
    ]

    def top(cat: str) -> list[CategoryShare]:
        return [
            CategoryShare(
                code=str(r.get("code") or r.get("id") or ""),
                name=str(r.get("name") or ""),
                obligations=float(r.get("amount") or 0.0),
            )
            for r in _category(recipient_id, cat, window, settings=settings, limit=8)
        ]

    # The agency split sums ALL awarding agencies (limit high enough to be exhaustive), not a top-N.
    defense = civilian = 0.0
    for r in _category(recipient_id, "awarding_agency", window, settings=settings, limit=100):
        amount = float(r.get("amount") or 0.0)
        if str(r.get("name") or "") in _DEFENSE_AGENCIES:
            defense += amount
        else:
            civilian += amount
    split_total = defense + civilian
    return {
        "breakdown_window": f"{window[0]}..{window[1]}",
        "annual_obligations": annual,
        "by_psc": top("psc"),
        "by_naics": top("naics"),
        "defense_obligations": defense,
        "civilian_obligations": civilian,
        "defense_share": (defense / split_total) if split_total > 0 else None,
    }


# --- Resolution ------------------------------------------------------------
def resolve_recipient(
    name: str,
    recipient_id: str,
    expected_uei: str,
    *,
    lei: str | None = None,
    nexus: str = "context",
    note: str | None = None,
    breakdown: bool = False,
    annual_years: list[int] | None = None,
    settings: Settings | None = None,
) -> RecipientAward | AwardLead:
    """Resolve one pinned recipient by id; verify the returned UEI matches the pin.

    With ``breakdown=True`` the record also carries the annual flow + PSC/NAICS mix + a
    defense-vs-civilian split (``annual_years`` are the fiscal years the flow covers; default the
    trailing ``settings.usaspending_annual_span_years``). ``breakdown=False`` keeps the lean,
    single-call resolution the unit path and offline fixtures rely on.
    """
    settings = settings or get_settings()
    prof = _profile(recipient_id, settings=settings)
    got_uei = prof.get("uei")
    if got_uei != expected_uei:
        return AwardLead(
            name=name,
            recipient_id=recipient_id,
            uei=expected_uei,
            note=f"UEI mismatch: profile returned {got_uei!r}, expected {expected_uei!r}",
        )
    extra: dict[str, Any] = {}
    if breakdown:
        if annual_years is None:
            end_fy = _current_fiscal_year(_dt.date.today())
            span = max(1, settings.usaspending_annual_span_years)
            annual_years = list(range(end_fy - span + 1, end_fy + 1))
        extra = _resolve_breakdown(recipient_id, annual_years=annual_years, settings=settings)
    return RecipientAward(
        watchlist_name=name,
        recipient_id=recipient_id,
        uei=got_uei,
        recipient_name=str(prof.get("name") or name),
        lei=lei,
        duns=prof.get("duns"),
        recipient_level=prof.get("recipient_level"),
        total_obligations=float(prof.get("total_transaction_amount") or 0.0),
        parent_name=prof.get("parent_name"),
        parent_uei=prof.get("parent_uei"),
        nexus=nexus,
        note=note,
        **extra,
    )


def _watchlist_path(settings: Settings) -> Path:
    """The active site's watchlist (Lima keeps the flat file; a peer reads its own #1662)."""
    base = site_scoped_path(settings.entities_dir, settings.site, is_dir=True)
    return base.joinpath(*_WATCHLIST_REL)


def resolve_watchlist(settings: Settings | None = None) -> UsaSpendingInventory:
    """Resolve every pinned recipient in the active site's watchlist.

    Lima reads the flat committed watchlist; a sibling site reads its own slug-scoped copy, and a
    site with none resolves to an empty inventory (the feed then degrades — never Lima's, #1662).
    The optional breakdown is driven by ``settings.usaspending_breakdown``.
    """
    settings = settings or get_settings()
    path = _watchlist_path(settings)
    if not path.is_file():
        return _empty_inventory(settings.site)
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    breakdown = settings.usaspending_breakdown
    records: list[RecipientAward] = []
    leads: list[AwardLead] = []
    for r in spec.get("recipients") or []:
        out = resolve_recipient(
            r["name"],
            r["recipient_id"],
            r["uei"],
            lei=r.get("lei"),
            nexus=r.get("nexus", "context"),
            note=r.get("note"),
            breakdown=breakdown,
            settings=settings,
        )
        (records if isinstance(out, RecipientAward) else leads).append(out)  # type: ignore[arg-type]
    for lead in spec.get("leads") or []:
        leads.append(AwardLead(**lead))

    spec_meta = spec.get("meta") or {}
    caveats = [
        "Totals are all-time prime-award obligations as reported by USASpending "
        "(total_transaction_amount, year=all), recorded verbatim — not BOSC estimates.",
        "Recipients are pinned by recipient_id + UEI; a UEI mismatch drops to a lead.",
        "The `nexus` tag distinguishes a verified corridor tie from context/open.",
    ]
    if breakdown:
        caveats.append(
            "The annual flow, PSC/NAICS mix, and defense-vs-civilian split are verbatim "
            "USASpending category rollups over the recorded window; the split classifies the "
            "DoD toptier (and military departments) as defense, all other agencies as civilian."
        )
    # A per-site watchlist supplies its own site-specific caveats (e.g. Lima's Amazon-warehouse /
    # Google-Dazzler nexus notes) via `meta.caveats`, so the federal layer is never Lima-anchored.
    caveats.extend(str(c) for c in (spec_meta.get("caveats") or []))
    meta = {
        "subject": spec_meta.get(
            "subject", "USASpending federal-award totals — real-party-in-interest"
        ),
        "site": settings.site,
        "source": _SOURCE,
        "award_window": "all-time prime-award obligations (year=all)",
        "breakdown": breakdown,
        "recipient_count": len(records),
        "verified_nexus_count": sum(1 for r in records if r.nexus == "verified"),
        "caveats": caveats,
    }
    return UsaSpendingInventory(meta=meta, records=records, leads=leads)


def _empty_inventory(site: str) -> UsaSpendingInventory:
    """The inventory a site with no watchlist resolves to — records absent, not Lima's."""
    return UsaSpendingInventory(
        meta={
            "subject": "USASpending federal-award totals — real-party-in-interest",
            "site": site,
            "source": _SOURCE,
            "recipient_count": 0,
            "verified_nexus_count": 0,
            "caveats": [f"No USASpending watchlist committed for site {site!r}."],
        },
        records=[],
        leads=[],
    )


# --- Persistence -----------------------------------------------------------
def awards_dir(reference_dir: Path, site: str = _REFERENCE_SITE) -> Path:
    """The active site's committed USASpending directory (Lima flat, a peer slug-scoped #1662)."""
    return site_scoped_path(reference_dir / "usaspending", site, is_dir=True)


def write_inventory(inv: UsaSpendingInventory, out_dir: Path) -> Path:
    """Write the resolution to ``<out_dir>/awards.yaml`` (deterministic)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "awards.yaml"
    path.write_text(
        yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_inventory(reference_dir: Path, site: str = _REFERENCE_SITE) -> UsaSpendingInventory | None:
    """Load the active site's committed USASpending awards, or ``None`` if absent.

    Lima reads the flat ``reference/usaspending/awards.yaml``; a peer reads its own
    slug-scoped ``reference/usaspending/<slug>/awards.yaml`` (absent → ``None``, so the
    peer's federal layer is empty rather than inheriting Lima's, #1662).
    """
    path = awards_dir(reference_dir, site) / "awards.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return UsaSpendingInventory(**data)
