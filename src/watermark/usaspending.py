"""USASpending federal-award resolution — "who benefits from federal dollars".

Resolves a pinned recipient watchlist
(``data/entities/profiles/usaspending-watchlist.yaml``) against the public
USASpending.gov API and commits the result to
``data/reference/usaspending/awards.yaml`` (regenerate with ``watermark usaspending``).

Discipline mirrors :mod:`watermark.gleif`: each recipient is pinned by its USASpending
``recipient_id`` **and** ``uei``; resolution fetches the recipient profile by id and
**asserts the returned UEI equals the pinned one** — never a fuzzy name match — so the
committed artifact is litigation-clean. Totals are **all-time prime-award
obligations** (``?year=all``, the API's ``total_transaction_amount``), recorded
verbatim. Each record keeps a ``nexus`` tag (verified / context / open) so the federal
layer never overclaims a corridor connection.

Raw API responses cache under the git-ignored ``data/cache/usaspending/``; only the
small curated YAML is committed.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel

from watermark.config import Settings, get_settings
from watermark.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

_SOURCE = "USASpending.gov API (api.usaspending.gov), U.S. Treasury; public domain"
_WATCHLIST_REL = ("profiles", "usaspending-watchlist.yaml")


class UsaSpendingOfflineError(RuntimeError):
    """Raised when offline mode needs an uncached USASpending response."""


# --- Models ----------------------------------------------------------------
class RecipientAward(BaseModel):
    """One resolved recipient's all-time federal prime-award obligations."""

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


def _profile(recipient_id: str, *, settings: Settings) -> dict[str, Any]:
    """The all-time recipient profile for a pinned recipient_id."""
    data = _request("GET", f"/recipient/{recipient_id}/?year=all", None, settings=settings)
    return data if isinstance(data, dict) else {}


# --- Resolution ------------------------------------------------------------
def resolve_recipient(
    name: str,
    recipient_id: str,
    expected_uei: str,
    *,
    lei: str | None = None,
    nexus: str = "context",
    note: str | None = None,
    settings: Settings | None = None,
) -> RecipientAward | AwardLead:
    """Resolve one pinned recipient by id; verify the returned UEI matches the pin."""
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
    )


def _watchlist_path(settings: Settings) -> Path:
    return settings.entities_dir.joinpath(*_WATCHLIST_REL)


def resolve_watchlist(settings: Settings | None = None) -> UsaSpendingInventory:
    """Resolve every pinned recipient in the committed watchlist."""
    settings = settings or get_settings()
    spec = yaml.safe_load(_watchlist_path(settings).read_text(encoding="utf-8")) or {}
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
            settings=settings,
        )
        (records if isinstance(out, RecipientAward) else leads).append(out)  # type: ignore[arg-type]
    for lead in spec.get("leads") or []:
        leads.append(AwardLead(**lead))

    meta = {
        "subject": "USASpending federal-award totals — corridor real-party-in-interest",
        "source": _SOURCE,
        "award_window": "all-time prime-award obligations (year=all)",
        "recipient_count": len(records),
        "verified_nexus_count": sum(1 for r in records if r.nexus == "verified"),
        "caveats": [
            "Totals are all-time prime-award obligations as reported by USASpending "
            "(total_transaction_amount, year=all), recorded verbatim — not BOSC estimates.",
            "Recipients are pinned by recipient_id + UEI; a UEI mismatch drops to a lead.",
            "The `nexus` tag distinguishes a verified corridor tie from context/open — the "
            "Amazon corridor recipient is a warehouse, NOT the data center, and Google is "
            "linked only to the separate Scioto Project Dazzler, not the Lima campus.",
        ],
    }
    return UsaSpendingInventory(meta=meta, records=records, leads=leads)


# --- Persistence -----------------------------------------------------------
def write_inventory(inv: UsaSpendingInventory, out_dir: Path) -> Path:
    """Write the resolution to ``<out_dir>/awards.yaml`` (deterministic)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "awards.yaml"
    path.write_text(
        yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_inventory(reference_dir: Path) -> UsaSpendingInventory | None:
    """Load the committed USASpending awards, or ``None`` if absent."""
    path = reference_dir / "usaspending" / "awards.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return UsaSpendingInventory(**data)
