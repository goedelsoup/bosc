"""Does production actually serve the documents the site offers? (#2149)

``DocumentItem.published`` is an assertion about a store the build never touches, and
``DocumentItem.available`` is computed from the *working tree* — where an unresolved Git-LFS
pointer counts as available on purpose, because the bytes are supposed to live in R2. So the feed
asserts serveability twice over and verifies it never. On 2026-09-04, of the **392** documents the
deployed build offered, 26 could be downloaded: 9 were absent from R2 and 357 were rejected by a
publish gate that only knew Lima's set (#2149's two independent causes).

This module is the check that was missing. It compares three sets and names which one broke:

===============  ==========================================================================
``offered``      what the repo publishes at this commit — the committed ``web/sites/<slug>``
                 bundles, unioned over the sites the build exports
``gate``         what the *deployed* ``/published-documents.json`` admits
``served``       what ``HEAD /api/doc/<rel>`` actually returns 200 for
===============  ==========================================================================

The decomposition is the point, because the three failures have three different fixes:

``unserved``     in the gate, not served — **production offers a download that 404s.** Always a
                 bug, whatever the repo looks like, so this is what exits nonzero.
``ungated``      offered, not in the gate — the deployed build is behind this commit. Routine
                 after a merge and *not* an error; a count far larger than recent commits
                 explain is the shape of a scoping bug, which is how #2149 read.
``store-absent`` offered, and the object is not in R2 at all (needs ``--via store``). No deploy
                 fixes it — ``watermark objectstore sync`` does.

``/api/doc`` answers 404 for both "not allowlisted" and "not in the store", so the API probe alone
cannot tell them apart; that is why ``store`` mode exists and why the two are reported separately
rather than summed into one number.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from watermark.config import repo_committed_bundles_dir
from watermark.logging import get_logger

log = get_logger(__name__)

#: The build-time asset the ``/api/doc`` Function reads its allowlist from (web/functions/api/
#: _lib/docAllowlist.ts). Path, not a full URL — it is resolved against the probed origin.
GATE_ASSET_PATH = "/published-documents.json"

#: How many HEADs run at once. Small on purpose: the probe is a health check on someone else's
#: production, not a load test, and Cloudflare throttles (the #2145 vault push learned this).
DEFAULT_CONCURRENCY = 8


class GateUnavailableError(RuntimeError):
    """The deployed allowlist asset could not be read, so no comparison is possible."""


# --- what the repo offers -----------------------------------------------------
@dataclass(frozen=True)
class OfferedRel:
    """One published document, and which exported sites publish it."""

    rel: str  # data/documents-relative — also the R2 key and the /api/doc path
    sites: tuple[str, ...]


def exported_slugs() -> list[str]:
    """The sites the Astro build exports a bundle for — ``selectable`` in ``data/sites.yaml``.

    The Python peer of ``@watermark/core``'s ``exportedSiteSlugs()``. Both read the same
    ``data/sites.yaml`` (the frontend through the generated ``sites-registry.json``), so the two
    cannot disagree about *which* sites without ``watermark sites sync`` being stale — which
    ``watermark sites check`` already gates.
    """
    from watermark.sites import _get_identity

    return [slug for slug, entry in _get_identity().items() if entry.selectable]


def offered_rels(
    *, bundles_root: Path | None = None, slugs: Sequence[str] | None = None
) -> list[OfferedRel]:
    """Every published rel across the exported sites' committed bundles, sorted.

    Read from ``web/sites/`` rather than re-derived from ``data/`` for two reasons: it is the same
    artifact the offline build reads (so this measures what a deploy of *this commit* would
    offer), and it needs no Git-LFS checkout, so the check runs anywhere.
    """
    root = bundles_root or repo_committed_bundles_dir()
    by_rel: dict[str, list[str]] = {}
    for slug in slugs if slugs is not None else exported_slugs():
        feed = root / slug / "feeds" / "documents.json"
        if not feed.is_file():
            log.warning("no committed documents feed for exported site", slug=slug)
            continue
        collections = json.loads(feed.read_text(encoding="utf-8"))
        for coll in collections:
            for entry in coll.get("entries", []):
                if entry.get("published"):
                    by_rel.setdefault(entry["rel"], []).append(slug)
    return [OfferedRel(rel=rel, sites=tuple(sites)) for rel, sites in sorted(by_rel.items())]


# --- what production admits and serves ----------------------------------------
def doc_api_path(rel: str) -> str:
    """The ``/api/doc/<rel>`` path for ``rel`` — per-segment encoded.

    Mirrors ``@watermark/core``'s ``docApiUrl``: each segment is encoded separately so the
    separators survive and a space or ``#`` in an as-received filename does not.
    """
    return "/api/doc/" + "/".join(urllib.parse.quote(s, safe="") for s in rel.split("/"))


def fetch_gate(base_url: str, *, client: httpx.Client) -> frozenset[str]:
    """The deployed allowlist — what the Function will admit right now."""
    url = base_url.rstrip("/") + GATE_ASSET_PATH
    try:
        resp = client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise GateUnavailableError(f"could not read {url}: {exc}") from exc
    rels = payload.get("rels")
    if not isinstance(rels, list):
        raise GateUnavailableError(f"{url} carries no `rels` array")
    return frozenset(str(r) for r in rels)


def probe_api(
    rels: Sequence[str],
    base_url: str,
    *,
    client: httpx.Client,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[str, int]:
    """``HEAD /api/doc/<rel>`` for each rel → its status code (``-1`` on a transport error).

    HEAD, not GET: the question is whether the object resolves, and the corpus is 3.7 GB.
    """
    root = base_url.rstrip("/")

    def one(rel: str) -> tuple[str, int]:
        try:
            resp = client.request("HEAD", root + doc_api_path(rel))
        except httpx.HTTPError as exc:
            log.warning("doc probe failed", rel=rel, error=str(exc))
            return rel, -1
        return rel, resp.status_code

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return dict(pool.map(one, rels))


def probe_store(
    rels: Sequence[str],
    head: Callable[[str], object | None],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> frozenset[str]:
    """The rels the object store does **not** hold, via ``head`` (an :class:`R2Store`-shaped call)."""

    def one(rel: str) -> tuple[str, bool]:
        return rel, head(rel) is not None

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return frozenset(rel for rel, present in pool.map(one, rels) if not present)


# --- the verdict (pure) -------------------------------------------------------
@dataclass(frozen=True)
class DocFinding:
    """One document that does not reach a reader, and which of the three sets failed it."""

    rel: str
    kind: str  # "unserved" | "ungated" | "store-absent"
    detail: str


@dataclass
class ServingAudit:
    """The comparison, decomposed. ``ok`` is the gating question; the rest is diagnosis."""

    base_url: str
    offered: int
    gate_size: int
    served: int
    unserved: list[DocFinding] = field(default_factory=list)
    ungated: list[DocFinding] = field(default_factory=list)
    store_absent: list[DocFinding] = field(default_factory=list)
    #: rels the gate admits that this commit does not offer — a deploy AHEAD of the checkout, or
    #: a clearance reverted without a redeploy. Reported, never gating.
    gate_only: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing production offers is unservable.

        ``ungated`` is excluded deliberately: a merged-but-undeployed clearance is the normal
        state of this repo between deploys, and a check that fails on it would be muted within a
        week. ``store_absent`` IS included — it is the failure no deploy can fix.
        """
        return not self.unserved and not self.store_absent


def classify(
    offered: Sequence[OfferedRel],
    gate: frozenset[str],
    statuses: dict[str, int],
    *,
    store_absent: frozenset[str] | None = None,
) -> tuple[list[DocFinding], list[DocFinding], list[DocFinding], list[str]]:
    """Split the three failure kinds out of the three sets. Pure — the tested core."""
    unserved: list[DocFinding] = []
    ungated: list[DocFinding] = []
    absent: list[DocFinding] = []
    for item in offered:
        code = statuses.get(item.rel)
        where = ", ".join(item.sites)
        if item.rel not in gate:
            ungated.append(
                DocFinding(
                    rel=item.rel,
                    kind="ungated",
                    detail=f"published by {where}; the deployed gate does not admit it",
                )
            )
        elif code != 200:
            unserved.append(
                DocFinding(
                    rel=item.rel,
                    kind="unserved",
                    detail=f"gate admits it; /api/doc answered {code}",
                )
            )
        if store_absent is not None and item.rel in store_absent:
            absent.append(
                DocFinding(
                    rel=item.rel,
                    kind="store-absent",
                    detail=f"published by {where}; no object in the store — run `objectstore sync`",
                )
            )
    offered_set = {i.rel for i in offered}
    return unserved, ungated, absent, sorted(gate - offered_set)


def audit(
    *,
    base_url: str,
    bundles_root: Path | None = None,
    slugs: Sequence[str] | None = None,
    client: httpx.Client | None = None,
    store_head: Callable[[str], object | None] | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> ServingAudit:
    """Run the full comparison against ``base_url``.

    ``store_head`` opts into the store probe (an :class:`R2Store`'s ``head``); without it the
    audit reports what production does and stays silent about *why* a 404 is a 404.
    """
    offered = offered_rels(bundles_root=bundles_root, slugs=slugs)
    owned = client is None
    http = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        gate = fetch_gate(base_url, client=http)
        rels = [i.rel for i in offered]
        statuses = probe_api(rels, base_url, client=http, concurrency=concurrency)
    finally:
        if owned:
            http.close()
    absent = probe_store(rels, store_head, concurrency=concurrency) if store_head else None
    unserved, ungated, store_absent, gate_only = classify(
        offered, gate, statuses, store_absent=absent
    )
    return ServingAudit(
        base_url=base_url,
        offered=len(offered),
        gate_size=len(gate),
        served=sum(1 for code in statuses.values() if code == 200),
        unserved=unserved,
        ungated=ungated,
        store_absent=store_absent,
        gate_only=gate_only,
    )


def findings(audit_result: ServingAudit) -> Iterable[DocFinding]:
    """Every finding, worst first — the two gating kinds before the reported one."""
    yield from audit_result.unserved
    yield from audit_result.store_absent
    yield from audit_result.ungated
