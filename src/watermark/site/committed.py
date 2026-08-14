"""The committed per-site bundles: writing them safely, and telling when they've gone stale (#2025).

``web/sites/<slug>/`` holds a committed ``watermark export`` for every registered site — the
offline input the Astro build reads with no Python step. It is a *build artifact of the corpus*,
and nothing recomputes it: an ingest that lands a document, a connector re-pull, a corrected
figure all move what an export would produce while the committed bundle sits unchanged, and the
site keeps serving the older answer until somebody re-exports for an unrelated reason. That has
now cost review attention in three consecutive PRs of one epic (#2021, #2022, #2023), each time
discovered while doing something else.

Two halves, sharing one definition of what a committed bundle *is*:

- :func:`check_committed_bundle` re-exports a site to a temp dir and reports how the committed
  tree differs — feed set, per-feed row counts, feed **bytes**, and the manifest's own claims
  (contract version, readiness, facility). Bytes matter as much as counts: a corrected figure
  inside a row moves no count at all.
- :func:`refresh_committed_bundle` writes that same normalized export into ``web/sites/<slug>/``.

**The lean trim.** A committed bundle is not a raw export. It drops ``schemas/`` (the site-agnostic
contract lives once at ``data/site/bundle/schemas/``) and the two page-level retrieval indexes,
``passages`` / ``passage-embeddings`` — both files *and* their manifest rows, since a manifest that
declares a feed whose file is absent makes the static build ``ENOENT``. Some sites deliberately
commit their passages anyway.

Which sites those are has been the sharp edge. ``web/sites/README.md`` carried the trim as a shell
snippet with a hardcoded exception list that "went stale within one issue of being written", and
running the drop step across the fleet has silently deleted committed retrieval evidence twice
(#1969, then #1993). So the exception set is not a list here: **a site keeps its retrieval indexes
if its own committed manifest already declares them**. The tree describes itself, there is nothing
to keep in sync, and the check and the writer read the rule from the same place.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watermark.config import Settings, get_settings, repo_committed_bundles_dir
from watermark.logging import get_logger

log = get_logger(__name__)

# The page-level retrieval indexes (#1589). Large, LFS-resolution dependent, and rebuilt from the
# shared `data/site/passages.ndjson` rather than from a site's own corpus — so the lean committed
# bundle omits them unless the site has chosen otherwise.
RETRIEVAL_FEEDS = ("passages", "passage-embeddings")

# `manifest.generated_at` is the one field that legitimately differs between two exports of an
# unchanged corpus, so it is never a finding. Everything else in the manifest is a claim about
# content and is compared.
_VOLATILE_MANIFEST_KEYS = frozenset({"generated_at"})


@dataclass(frozen=True)
class BundleFinding:
    """One way a committed bundle differs from what the corpus would export today."""

    slug: str
    kind: str  # absent | manifest | missing-feed | stale-feed | count | content | file
    subject: str  # the feed name, or the manifest key
    detail: str

    def __str__(self) -> str:
        return f"{self.slug}: [{self.kind}] {self.subject} — {self.detail}"


@dataclass(frozen=True)
class RefreshReport:
    """What :func:`refresh_committed_bundle` installed."""

    slug: str
    out_dir: Path
    feed_count: int
    row_total: int
    retrieval_kept: bool


def committed_bundle_dir(slug: str, *, root: Path | None = None) -> Path:
    """The committed bundle directory for ``slug`` (``web/sites/<slug>/``)."""
    return (root or repo_committed_bundles_dir()) / slug


def site_settings(slug: str, base: Settings | None = None) -> Settings:
    """A ``Settings`` for ``slug``, built fresh so the per-site profile knobs are re-filled.

    Constructed rather than ``model_copy``'d on purpose: ``PROFILE_SETTINGS_FIELDS`` are filled
    by a model validator from the active profile, so copying an existing instance with a new
    ``site`` would carry the *previous* site's gage ids, FIPS and GIS URLs into the new one.
    """
    base = base or get_settings()
    return Settings(site=slug, data_dir=base.data_dir)


def _read_manifest(bundle: Path) -> dict[str, Any] | None:
    path = bundle / "manifest.json"
    if not path.is_file():
        return None
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _keeps_retrieval_feeds(committed: Path) -> bool:
    """Does this site's committed bundle already declare the retrieval indexes?

    The committed manifest is the authority (see the module docstring) — not a list in this file
    and not one in the README, both of which have gone stale in practice. A site with no committed
    bundle yet defaults to the lean shape.
    """
    manifest = _read_manifest(committed)
    if manifest is None:
        return False
    return any(f["name"] in RETRIEVAL_FEEDS for f in manifest.get("feeds", []))


def _apply_lean_trim(bundle: Path, *, keep_retrieval: bool) -> None:
    """Turn a raw export in ``bundle`` into the committed shape, in place."""
    shutil.rmtree(bundle / "schemas", ignore_errors=True)
    if keep_retrieval:
        return
    manifest = _read_manifest(bundle)
    if manifest is None:  # pragma: no cover — export always writes one
        return
    for ref in manifest["feeds"]:
        if ref["name"] in RETRIEVAL_FEEDS:
            (bundle / ref["path"]).unlink(missing_ok=True)
    manifest["feeds"] = [f for f in manifest["feeds"] if f["name"] not in RETRIEVAL_FEEDS]
    manifest["feed_count"] = len(manifest["feeds"])
    manifest["row_total"] = sum(f["count"] for f in manifest["feeds"])
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _export_lean(slug: str, dest: Path, *, base: Settings | None, keep_retrieval: bool) -> None:
    """Export ``slug`` into ``dest`` and normalize it to the committed shape.

    ``skip_embeddings`` matches how the committed tree is built (``--no-embeddings``: the
    ``ask-embeddings`` feed ships present-but-empty), and passing ``out_dir`` is what keeps the
    export from clobbering the repo's canonical ``.yidam/`` mirror and from rendering the
    ``exports/`` graph artifacts the committed bundles do not carry.
    """
    from watermark.site.export import export_bundle

    export_bundle(
        site_settings(slug, base),
        out_dir=dest,
        skip_embeddings=True,
    )
    _apply_lean_trim(dest, keep_retrieval=keep_retrieval)


def _rows(bundle: Path, ref: dict[str, Any]) -> list[Any]:
    """A feed's rows, whatever its media type — so a content diff can point at one."""
    text = (bundle / ref["path"]).read_text(encoding="utf-8")
    if ref["media_type"] == "application/x-ndjson":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    parsed = json.loads(text)
    return parsed if ref["kind"] == "collection" else [parsed]


def _first_differing_row(committed: Path, fresh: Path, ref: dict[str, Any]) -> str:
    """A pointer at the first row that moved, so the report is actionable without a full dump."""
    try:
        old, new = _rows(committed, ref), _rows(fresh, ref)
    except (OSError, json.JSONDecodeError):  # pragma: no cover — a corrupt feed is its own finding
        return "content differs (unparseable)"
    for i, (a, b) in enumerate(zip(old, new, strict=False)):
        if a == b:
            continue
        # Naming the fields only makes sense for object rows; a geo layer's single row or a
        # scalar one just reports its index. Guarded before the key union so a non-dict row
        # can't raise inside a reporting path.
        if isinstance(a, dict) and isinstance(b, dict):
            changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            if changed:
                return f"content differs from row {i}, fields: {', '.join(changed)}"
        return f"content differs from row {i}"
    return "content differs"


def _compare_manifests(
    slug: str, committed: dict[str, Any], fresh: dict[str, Any]
) -> list[BundleFinding]:
    """Every manifest claim except the feed list and the timestamp."""
    findings: list[BundleFinding] = []
    for key in sorted((set(committed) | set(fresh)) - _VOLATILE_MANIFEST_KEYS - {"feeds"}):
        old, new = committed.get(key), fresh.get(key)
        if old == new:
            continue
        findings.append(
            BundleFinding(
                slug=slug,
                kind="manifest",
                subject=key,
                detail=f"committed {json.dumps(old, sort_keys=True)} != fresh "
                f"{json.dumps(new, sort_keys=True)}",
            )
        )
    return findings


def check_committed_bundle(
    slug: str,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> list[BundleFinding]:
    """Report how ``web/sites/<slug>/`` differs from what the corpus would export today.

    An empty list means the committed bundle is current. The export is deterministic apart from
    ``manifest.generated_at``, so everything else compares byte-for-byte and a finding is a real
    difference rather than a re-serialization artifact.
    """
    committed = committed_bundle_dir(slug, root=root)
    committed_manifest = _read_manifest(committed)
    if committed_manifest is None:
        return [
            BundleFinding(
                slug=slug,
                kind="absent",
                subject=f"web/sites/{slug}",
                detail="registered site has no committed bundle — run "
                f"`watermark --site {slug} export --committed`",
            )
        ]

    with tempfile.TemporaryDirectory(prefix=f"bundle-check-{slug}-") as td:
        fresh_dir = Path(td) / slug
        _export_lean(
            slug,
            fresh_dir,
            base=settings,
            keep_retrieval=_keeps_retrieval_feeds(committed),
        )
        fresh_manifest = _read_manifest(fresh_dir) or {"feeds": []}
        findings = _compare_manifests(slug, committed_manifest, fresh_manifest)
        findings += _compare_feeds(slug, committed, fresh_dir, committed_manifest, fresh_manifest)

    log.info("bundle.checked", site=slug, findings=len(findings))
    return findings


def _compare_feeds(
    slug: str,
    committed: Path,
    fresh_dir: Path,
    committed_manifest: dict[str, Any],
    fresh_manifest: dict[str, Any],
) -> list[BundleFinding]:
    """The feed set, then each shared feed's row count, then its bytes."""
    findings: list[BundleFinding] = []
    committed_refs = {f["name"]: f for f in committed_manifest["feeds"]}
    fresh_refs = {f["name"]: f for f in fresh_manifest["feeds"]}

    for name in sorted(set(fresh_refs) - set(committed_refs)):
        findings.append(
            BundleFinding(
                slug,
                "missing-feed",
                name,
                f"the export produces it ({fresh_refs[name]['count']} rows); "
                "the committed bundle does not carry it",
            )
        )
    for name in sorted(set(committed_refs) - set(fresh_refs)):
        findings.append(
            BundleFinding(
                slug, "stale-feed", name, "committed, but the export no longer produces it"
            )
        )

    for name in sorted(set(committed_refs) & set(fresh_refs)):
        old_ref, new_ref = committed_refs[name], fresh_refs[name]
        old_file, new_file = committed / old_ref["path"], fresh_dir / new_ref["path"]
        if not old_file.is_file():
            findings.append(
                BundleFinding(
                    slug, "file", name, f"manifest declares {old_ref['path']}, which is absent"
                )
            )
        elif old_ref["count"] != new_ref["count"]:
            findings.append(
                BundleFinding(
                    slug,
                    "count",
                    name,
                    f"committed {old_ref['count']} rows != fresh {new_ref['count']}",
                )
            )
        elif old_file.read_bytes() != new_file.read_bytes():
            findings.append(
                BundleFinding(
                    slug, "content", name, _first_differing_row(committed, fresh_dir, old_ref)
                )
            )
    return findings


def refresh_committed_bundle(
    slug: str,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
    keep_retrieval: bool | None = None,
) -> RefreshReport:
    """Rewrite ``web/sites/<slug>/`` from the corpus, in the committed (lean) shape.

    The export lands in a temp dir and is normalized there; the committed tree is only replaced
    once that has succeeded. A half-written export therefore leaves the committed bundle alone
    rather than corrupting it, and the replace (rather than an overlay) is what retires a feed the
    exporter no longer produces instead of leaving it behind.

    ``keep_retrieval`` defaults to what the site's committed manifest already declares, so a site
    that ships its ``passages`` index keeps shipping it without anyone maintaining a list.
    """
    target = committed_bundle_dir(slug, root=root)
    keep = _keeps_retrieval_feeds(target) if keep_retrieval is None else keep_retrieval

    with tempfile.TemporaryDirectory(prefix=f"bundle-refresh-{slug}-") as td:
        staged = Path(td) / slug
        _export_lean(slug, staged, base=settings, keep_retrieval=keep)
        manifest = _read_manifest(staged) or {"feed_count": 0, "row_total": 0}
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, target)

    log.info(
        "bundle.refreshed",
        site=slug,
        feeds=manifest["feed_count"],
        rows=manifest["row_total"],
        retrieval=keep,
    )
    return RefreshReport(
        slug=slug,
        out_dir=target,
        feed_count=manifest["feed_count"],
        row_total=manifest["row_total"],
        retrieval_kept=keep,
    )
