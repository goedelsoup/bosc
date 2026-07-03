"""GLEIF Legal Entity Identifier (LEI) resolution for corridor entities.

Resolves a curated **watchlist** of corridor / RSEI facility parent companies
(``data/entities/profiles/lei-watchlist.yaml``) against the GLEIF registry — the
global "who is who / who owns whom" directory — and writes a committed reference
table (``data/reference/gleif/lei-records.yaml``) with each entity's verified LEI,
legal name, jurisdiction, status, legal address, and reported direct / ultimate
parent. Regenerate with ``watermark lei``.

GLEIF's AWS Open Data bucket (``s3://gleif``) is the bulk golden copy (millions of
records, refreshed thrice daily); for a small watchlist we use GLEIF's REST API.
**Every LEI is pinned and fetched by exact 20-char ID** — never a fuzzy name match
— so the committed evidence can't drift onto the wrong legal entity. Entities whose
correct legal entity is ambiguous stay as unresolved *leads*, not pinned records.
Raw API responses cache under the git-ignored ``data/cache/gleif/``; only the
curated YAML is committed.

A parent relationship that returns 404 means GLEIF holds **no reported relationship
record** for that entity — recorded as ``None``, which is not a claim that no parent
exists (it may be an unreported reporting exception).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

_ACCEPT = "application/vnd.api+json"
_SOURCE = "GLEIF (AWS Open Data s3://gleif), REST API api.gleif.org; license CC0"


class GleifOfflineError(RuntimeError):
    """Raised when offline mode needs an uncached GLEIF response."""


# --- Models ----------------------------------------------------------------
class LeiRef(BaseModel):
    """A minimal reference to a related LEI entity (a parent)."""

    lei: str
    name: str


class LeiAddress(BaseModel):
    city: str | None = None
    region: str | None = None
    country: str | None = None


class LeiRecord(BaseModel):
    """A resolved LEI record for one watchlist entity."""

    watchlist_name: str
    lei: str
    legal_name: str
    jurisdiction: str | None = None
    legal_form: str | None = None
    entity_status: str | None = None  # ACTIVE / INACTIVE
    registration_status: str | None = None  # ISSUED / LAPSED / RETIRED ...
    last_update: str | None = None
    legal_address: LeiAddress | None = None
    direct_parent: LeiRef | None = None
    ultimate_parent: LeiRef | None = None
    note: str | None = None


class LeiLead(BaseModel):
    """A watchlist entity with no verified, unambiguous LEI pinned."""

    name: str
    query: str | None = None
    note: str | None = None


class LeiInventory(BaseModel):
    """The committed GLEIF resolution: provenance meta + records + unresolved leads."""

    meta: dict[str, Any]
    records: list[LeiRecord]
    leads: list[LeiLead] = []


# --- HTTP + cache ----------------------------------------------------------
def _cache_path(settings: Settings, path: str) -> Path:
    key = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return settings.gleif_cache_dir / f"{key}.json"


def _get(path: str, *, settings: Settings, allow_404: bool = False) -> dict[str, Any] | None:
    """GET an API path (cached). Returns parsed JSON, or None on an allowed 404."""
    cache = _cache_path(settings, path)
    if cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        return _unwrap(data, allow_404=allow_404)
    if settings.gleif_offline:
        raise GleifOfflineError(f"offline: no cached GLEIF response for {path} ({cache})")

    import httpx

    url = f"{settings.gleif_base_url}{path}"
    log.info("gleif.fetch", path=path)
    resp = httpx.get(url, headers={"Accept": _ACCEPT}, timeout=settings.gleif_request_timeout_s)
    if resp.status_code == 404 and allow_404:
        payload: dict[str, Any] = {"_status": 404}
    else:
        resp.raise_for_status()
        payload = resp.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return _unwrap(payload, allow_404=allow_404)


def _unwrap(payload: dict[str, Any], *, allow_404: bool) -> dict[str, Any] | None:
    if payload.get("_status") == 404:
        return None
    return payload


# --- Resolution ------------------------------------------------------------
def _parent_ref(payload: dict[str, Any] | None) -> LeiRef | None:
    if not payload:
        return None
    data = payload.get("data")
    if not data:
        return None
    attrs = data.get("attributes", {})
    lei = attrs.get("lei")
    name = attrs.get("entity", {}).get("legalName", {}).get("name")
    if not lei or not name:
        return None
    return LeiRef(lei=lei, name=name)


def fetch_record(
    lei: str, *, watchlist_name: str, note: str | None = None, settings: Settings | None = None
) -> LeiRecord | None:
    """Fetch one LEI by exact ID plus its reported direct/ultimate parent."""
    settings = settings or get_settings()
    payload = _get(f"/lei-records/{lei}", settings=settings, allow_404=True)
    if payload is None or not payload.get("data"):
        return None
    attrs = payload["data"]["attributes"]
    ent = attrs.get("entity", {})
    addr = ent.get("legalAddress", {}) or {}
    direct = _get(f"/lei-records/{lei}/direct-parent", settings=settings, allow_404=True)
    ultimate = _get(f"/lei-records/{lei}/ultimate-parent", settings=settings, allow_404=True)
    return LeiRecord(
        watchlist_name=watchlist_name,
        lei=attrs.get("lei", lei),
        legal_name=ent.get("legalName", {}).get("name", ""),
        jurisdiction=ent.get("jurisdiction"),
        legal_form=(ent.get("legalForm") or {}).get("id"),
        entity_status=ent.get("status"),
        registration_status=(attrs.get("registration") or {}).get("status"),
        last_update=(attrs.get("registration") or {}).get("lastUpdateDate"),
        legal_address=LeiAddress(
            city=addr.get("city"), region=addr.get("region"), country=addr.get("country")
        ),
        direct_parent=_parent_ref(direct),
        ultimate_parent=_parent_ref(ultimate),
        note=note,
    )


def load_watchlist(entities_dir: Path) -> dict[str, Any] | None:
    """Load the curated LEI watchlist (profiles/lei-watchlist.yaml) if present."""
    path = entities_dir / "profiles" / "lei-watchlist.yaml"
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_watchlist(settings: Settings | None = None) -> LeiInventory:
    """Resolve every pinned watchlist entity to an LEI record; collect the leads."""
    settings = settings or get_settings()
    wl = load_watchlist(settings.entities_dir) or {}
    records: list[LeiRecord] = []
    for entry in wl.get("entities", []):
        lei = entry.get("lei")
        name = entry.get("name", lei)
        if not lei:
            continue
        rec = fetch_record(lei, watchlist_name=name, note=entry.get("note"), settings=settings)
        if rec is not None:
            records.append(rec)
        else:
            log.warning("gleif.unresolved", name=name, lei=lei)
    records.sort(key=lambda r: r.legal_name.upper())
    leads = [
        LeiLead(name=e.get("name", ""), query=e.get("query"), note=e.get("note"))
        for e in wl.get("leads", [])
    ]
    with_parent = sum(1 for r in records if r.ultimate_parent or r.direct_parent)
    return LeiInventory(
        meta={
            "subject": "GLEIF LEI resolution — corridor entity parents",
            "source": _SOURCE,
            "record_count": len(records),
            "with_reported_parent": with_parent,
            "lead_count": len(leads),
            "method": "pinned LEIs fetched by exact ID (no fuzzy name match)",
        },
        records=records,
        leads=leads,
    )


# --- Load / write ----------------------------------------------------------
def load_inventory(reference_dir: Path) -> LeiInventory | None:
    """Load the committed ``data/reference/gleif/lei-records.yaml`` if present."""
    path = reference_dir / "gleif" / "lei-records.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return LeiInventory.model_validate(data)


def write_inventory(inv: LeiInventory, out_dir: Path) -> Path:
    """Write the LEI resolution as deterministic YAML (no timestamp)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "lei-records.yaml"
    data = inv.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    return path
