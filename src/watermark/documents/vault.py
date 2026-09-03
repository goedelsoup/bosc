"""The committed record of the corpus' vaulted bytes (#2143, epic #2141).

`data/documents/**` is 3,643 files and 3,690 MB of public-records evidence, and Git-LFS is the
wrong place for it: that store ran out of budget mid-ingest, and #2074 had to defer 168 fetched,
screened documents for want of quota. The bytes move to a **yidam artifact vault** (RFC-0023) — a
content-addressed object store — and this module writes the half that stays in git:

    A vault stores bytes. Git stores the record of them.

Losing the vault then costs no knowledge claim, only the time to re-fetch, because every digest is
in a commit. That is the property the whole design rests on, and it is why this record is committed
rather than derived at push time.

**The record is nearly free, because the Git-LFS oid IS the sha256 a vault addresses by.** Both are
the SHA-256 of the file's content, so an unresolved pointer already carries its own content address
and its true size. :func:`content_address` exploits that with one uniform rule — hash the real
bytes when they are there, read the pointer when they are not — which makes a manifest generated on
a ``git lfs pull``ed working tree byte-identical to one generated on the CI checkout that never
pulled. `hearings-audio-externalized.yaml` asserted this for four hearing WAVs
(*"sha256 below are the authoritative Git-LFS oids"*); this generalizes its shape to the corpus.

**Granularity.** One `vault.yaml` per first-level collection under each vaulted root — 31 under
`documents/`, 4 under `reference/`. That matches `DocumentCollectionItem` and puts the record in the
same neighbourhood as the `MANIFEST.yaml` / `filename-map.yaml` / `text-sidecars.yaml` files a
reader already expects to find there.

**`rel` is `data_dir`-relative**, i.e. `documents/aedg/…` and `reference/usgs/…`, matching
`watermark.catalog.StorageItem.relpath` rather than `DocumentItem.rel`. The manifest spans two
roots, so a documents-relative key would be ambiguous between them; strip the `documents/` prefix
to recover the `/api/doc` key. Within that, the path is the **as-received name, verbatim** — three
files carry no extension and several carry upper-case ones, because a source filename is never
"fixed" (see `filename-map.yaml`).

**`redistributable` is written on every artifact and never defaulted.** This corpus is public
records (Ohio R.C. 149.43 productions, U.S. Government works) and nothing in it is licence-
encumbered, so the value is `True` throughout — but yidam refuses a push per-artifact, and the point
of that refusal is that a licence assertion should be something a person stated rather than an
absence. The first document obtained under a licence to read rather than to host needs the field to
already mean something. It is **not** derived from `data/site/published-documents.yaml`: that file
answers whether a document may be served from a searchable public site — a question about
aggregation, answered `no` for two files whose underlying records are public — which is not the same
question as whether the bytes may be stored.

**Duplicates are kept.** 476 of the 3,662 files are byte-duplicates of another (3,186 distinct
addresses). Every `rel` gets an entry: two custody paths to one blob is a fact about the corpus, and
`document-versions.yaml` already reasons about it. Collapsing them is the store's business — content
addressing does it for free — not the record's.

**Chain of custody.** Nothing here writes, renames, or reads-then-rewrites a byte under a vaulted
root. Every source is opened read-only; the only writes are the `vault.yaml` files themselves.

See `docs/artifact-vault.md` for the decisions behind all of the above.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.logging import get_logger

log = get_logger(__name__)

MANIFEST_NAME = "vault.yaml"

#: The `data_dir`-relative roots whose bytes are vaulted rather than committed. `documents/` is the
#: source corpus; `reference/` holds 19 large source PDFs behind derived datasets, scoped in by the
#: #2142 decision record. Both are enumerated from Git-LFS tracking, so a root with no tracked file
#: simply yields no manifest.
VAULTED_ROOTS: tuple[str, ...] = ("documents", "reference")

_POINTER_MAGIC = b"version https://git-lfs.github.com/spec/v1"
_OID_PREFIX = "oid sha256:"


@dataclass(frozen=True)
class LfsPointer:
    """An unresolved Git-LFS pointer's two load-bearing fields."""

    oid: str  # sha256 of the CONTENT — the same value a vault addresses by
    size: int  # the content's true size, not the pointer stub's


def parse_pointer(head: bytes) -> LfsPointer | None:
    """Parse a Git-LFS pointer from the head of a file, or ``None`` if it is not one.

    A pointer is short, line-oriented text: a ``version`` line, an ``oid sha256:<hex>`` line and a
    ``size <int>`` line. Both fields must be present and well-formed to return a pointer — a
    truncated or hand-mangled stub is *not* a pointer we can take a content address from, and
    saying so is better than reading a partial one as authoritative.
    """
    if not head.startswith(_POINTER_MAGIC):
        return None
    oid: str | None = None
    size: int | None = None
    for line in head.decode("utf-8", errors="replace").splitlines():
        if line.startswith(_OID_PREFIX):
            candidate = line[len(_OID_PREFIX) :].strip()
            if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate):
                oid = candidate
        elif line.startswith("size "):
            try:
                size = int(line[5:].strip())
            except ValueError:
                return None
    if oid is None or size is None:
        return None
    return LfsPointer(oid=oid, size=size)


def content_address(path: Path) -> tuple[str, int] | None:
    """``(sha256, bytes)`` for *path*, or ``None`` when it cannot be established.

    One rule, two branches, deliberately equivalent:

    * the real bytes are present — hash them;
    * the file is an unresolved Git-LFS pointer — take the oid and size it already carries, which
      *are* the content's sha256 and length.

    So the answer does not depend on whether the checkout ran ``git lfs pull``, which is what lets
    ``--check`` gate in CI and lets the manifest be written without materializing 3.7 GB. ``None``
    means the file is missing or unreadable, or is a pointer too mangled to trust — never a guess.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(256)
            pointer = parse_pointer(head)
            if pointer is not None:
                return (pointer.oid, pointer.size)
            digest = hashlib.sha256(head)
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return None
    return (digest.hexdigest(), path.stat().st_size)


class VaultArtifact(BaseModel):
    """One vaulted file: where it came from, and the address the vault holds it under."""

    model_config = ConfigDict(extra="forbid")

    rel: str  # data_dir-relative, as-received name verbatim (e.g. "documents/aedg/PRR-01…pdf")
    sha256: str  # the content address; equal to the Git-LFS oid while the file is LFS-tracked
    bytes: int
    media_type: str  # from the extension table alone — deterministic across checkouts
    # Always written, never defaulted: yidam refuses a push per-artifact, and the refusal only
    # means anything if the assertion was made rather than omitted. See the module docstring.
    redistributable: bool


class VaultMeta(BaseModel):
    """Provenance for one collection's manifest."""

    model_config = ConfigDict(extra="forbid")

    collection: str  # the data_dir-relative collection this manifest covers
    policy: str
    generated_at: str
    generated_by: str
    counts: dict[str, int]


class VaultManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: VaultMeta
    artifacts: list[VaultArtifact]


_POLICY = (
    "the committed record of bytes kept in a yidam artifact vault, not in git: `sha256` is the "
    "content address the vault holds each file under, and equals its Git-LFS oid while the file "
    "is still LFS-tracked. Regenerate with `watermark documents manifest`; verify with "
    "`--check`. Never hand-edit an entry — the next run reverts it. Losing the vault costs no "
    "claim, only a re-fetch, because every digest here is in a commit."
)

_GENERATED_BY = "watermark documents manifest"


def _suffix(rel: str) -> str:
    """The lower-cased, de-dotted extension, as ``DocumentItem.suffix`` carries it."""
    return PurePosixPath(rel).suffix.lstrip(".").lower()


def tracked_rels(repo_root: Path, data_dirname: str = "data") -> list[str]:
    """Every Git-LFS-tracked path under a vaulted root, as ``data_dir``-relative rels.

    Reads ``git lfs ls-files``, which resolves against the checked-out tree and ``.gitattributes``
    without any network or object fetch — so this is answerable on the shallow, ``lfs: false``
    checkouts CI and the agent workers use.

    Sorted, so a manifest's ordering is a property of the corpus rather than of the filesystem.
    """
    out = subprocess.run(
        ["git", "lfs", "ls-files", "--name-only"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    prefixes = tuple(f"{data_dirname}/{root}/" for root in VAULTED_ROOTS)
    rels = [
        line[len(data_dirname) + 1 :]
        for line in (raw.strip() for raw in out.splitlines())
        if line.startswith(prefixes)
    ]
    return sorted(rels)


def collection_of(rel: str) -> str:
    """The first-level collection a rel belongs to — ``documents/aedg`` for a file inside it.

    Raises for a rel with no collection component: every vaulted file lives in one, and inventing a
    root-level manifest for a file that should not be there would hide the anomaly.
    """
    parts = PurePosixPath(rel).parts
    if len(parts) < 3:
        raise ValueError(
            f"{rel!r} has no collection under its vaulted root — expected "
            "'<root>/<collection>/<path>'"
        )
    return f"{parts[0]}/{parts[1]}"


def manifest_path(data_dir: Path, collection: str) -> Path:
    return data_dir / collection / MANIFEST_NAME


def load_manifest(data_dir: Path, collection: str) -> VaultManifest | None:
    path = manifest_path(data_dir, collection)
    if not path.is_file():
        return None
    return VaultManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _artifact(data_dir: Path, rel: str) -> VaultArtifact | None:
    from watermark.site.documents import media_type_by_extension

    address = content_address(data_dir / rel)
    if address is None:
        return None
    sha256, size = address
    return VaultArtifact(
        rel=rel,
        sha256=sha256,
        bytes=size,
        media_type=media_type_by_extension(_suffix(rel)),
        # True throughout: a public-records corpus. Stated per artifact all the same — see the
        # module docstring on why this is not a default.
        redistributable=True,
    )


class UnaddressableError(RuntimeError):
    """Raised when a tracked file yields no content address, naming every offender.

    A manifest missing entries is worse than no manifest: it is a record that looks complete. So a
    run that cannot address a file refuses to write rather than silently omitting it — the same
    stance ``text_sidecars.generate`` takes when a conversion produces nothing.
    """


def build(
    data_dir: Path, repo_root: Path, *, rels: Iterable[str] | None = None
) -> list[VaultManifest]:
    """One :class:`VaultManifest` per collection holding at least one tracked file.

    *rels* overrides the Git-LFS enumeration (for tests, and for a narrowed run).
    """
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    wanted = sorted(rels) if rels is not None else tracked_rels(repo_root, data_dir.name)

    by_collection: dict[str, list[VaultArtifact]] = {}
    unaddressable: list[str] = []
    for rel in wanted:
        artifact = _artifact(data_dir, rel)
        if artifact is None:
            unaddressable.append(rel)
            continue
        by_collection.setdefault(collection_of(rel), []).append(artifact)

    if unaddressable:
        shown = "\n  ".join(unaddressable[:10])
        more = f"\n  … and {len(unaddressable) - 10} more" if len(unaddressable) > 10 else ""
        raise UnaddressableError(
            f"{len(unaddressable)} tracked file(s) yield no content address — refusing to write a "
            f"manifest that would read as complete:\n  {shown}{more}"
        )

    return [
        VaultManifest(
            meta=VaultMeta(
                collection=collection,
                policy=_POLICY,
                generated_at=now,
                generated_by=_GENERATED_BY,
                counts={
                    "artifacts": len(artifacts),
                    "bytes": sum(a.bytes for a in artifacts),
                    "distinct_addresses": len({a.sha256 for a in artifacts}),
                },
            ),
            artifacts=artifacts,
        )
        for collection, artifacts in sorted(by_collection.items())
    ]


def write(data_dir: Path, manifests: Iterable[VaultManifest]) -> list[Path]:
    """Write each manifest whose **artifacts** differ from the committed copy; return those paths.

    A collection whose artifacts are unchanged is left alone rather than rewritten with a fresh
    ``generated_at``. Without that, regenerating dirties all 35 files on every run and the diff
    stops carrying information — which matters here more than usual, because this record is reviewed
    the way an extraction is: by reading what changed. The timestamp then means *when this
    collection last moved*, which is the more useful claim anyway.
    """
    written: list[Path] = []
    for manifest in manifests:
        path = manifest_path(data_dir, manifest.meta.collection)
        existing = load_manifest(data_dir, manifest.meta.collection) if path.is_file() else None
        if existing is not None and existing.artifacts == manifest.artifacts:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
        written.append(path)
    return written


class VaultFinding(BaseModel):
    """One drift between the committed manifests and the tree they describe."""

    model_config = ConfigDict(extra="forbid")

    # unrecorded | duplicated | missing | address-changed | size-changed | media-changed |
    # orphaned — see check() for what each one means and why they are not equally severe.
    kind: str
    rel: str
    detail: str


def _iter_committed(data_dir: Path) -> Iterator[tuple[str, VaultArtifact]]:
    for root in VAULTED_ROOTS:
        root_dir = data_dir / root
        if not root_dir.is_dir():
            continue
        for path in sorted(root_dir.glob(f"*/{MANIFEST_NAME}")):
            collection = f"{root}/{path.parent.name}"
            manifest = load_manifest(data_dir, collection)
            if manifest is None:  # pragma: no cover - glob just found it
                continue
            for artifact in manifest.artifacts:
                yield collection, artifact


def check(
    data_dir: Path, repo_root: Path, *, rels: Iterable[str] | None = None
) -> list[VaultFinding]:
    """Report drift between the committed manifests and the tracked tree.

    Six kinds, and the asymmetry between them is the point:

    * ``unrecorded`` — tracked but in no manifest. **This is the one that matters most.** After the
      untrack (#2147) a file the manifest does not name is a source byte with no record at all,
      which is exactly the state the vault exists to make impossible.
    * ``orphaned`` — recorded but no longer tracked. Not automatically wrong (it is the expected
      state after #2147, when nothing is LFS-tracked any more), so callers pass ``rels`` explicitly
      when that transition lands; today an orphan means a file left the corpus without its record.
    * ``address-changed`` / ``size-changed`` — the bytes are not what the record claims. Since the
      address is the identity, this means a source file was replaced, which chain of custody
      forbids outright.
    * ``missing`` — recorded and tracked, but unreadable here. Reported rather than treated as
      drift: an absent file on a partial checkout is not evidence that the record is wrong.
    * ``media-changed`` — the extension table now types the file differently.
    * ``duplicated`` — one rel recorded by two manifests. ``exactly once`` is the invariant a
      record has to hold to be usable as one; two entries for a path make "what does the vault hold
      for this file" ambiguous even when both agree today.

    Needs neither the real bytes nor the network, by the same argument as :func:`content_address`.
    """
    from watermark.site.documents import media_type_by_extension

    tracked = set(sorted(rels) if rels is not None else tracked_rels(repo_root, data_dir.name))
    findings: list[VaultFinding] = []
    recorded: dict[str, VaultArtifact] = {}

    for collection, artifact in _iter_committed(data_dir):
        if artifact.rel in recorded:
            findings.append(
                VaultFinding(
                    kind="duplicated",
                    rel=artifact.rel,
                    detail=f"recorded twice — second occurrence in {collection}/{MANIFEST_NAME}",
                )
            )
            continue
        recorded[artifact.rel] = artifact

    for rel in sorted(tracked - recorded.keys()):
        findings.append(
            VaultFinding(
                kind="unrecorded",
                rel=rel,
                detail=f"Git-LFS tracked but named by no {MANIFEST_NAME}",
            )
        )

    for rel in sorted(recorded.keys() - tracked):
        findings.append(
            VaultFinding(
                kind="orphaned",
                rel=rel,
                detail=f"recorded in {MANIFEST_NAME} but no longer Git-LFS tracked",
            )
        )

    for rel in sorted(tracked & recorded.keys()):
        artifact = recorded[rel]
        address = content_address(data_dir / rel)
        if address is None:
            findings.append(
                VaultFinding(kind="missing", rel=rel, detail="not readable in this checkout")
            )
            continue
        sha256, size = address
        if sha256 != artifact.sha256:
            findings.append(
                VaultFinding(
                    kind="address-changed",
                    rel=rel,
                    detail=f"records {artifact.sha256[:12]}…, tree has {sha256[:12]}…",
                )
            )
        if size != artifact.bytes:
            findings.append(
                VaultFinding(
                    kind="size-changed",
                    rel=rel,
                    detail=f"records {artifact.bytes} bytes, tree has {size}",
                )
            )
        expected_media = media_type_by_extension(_suffix(rel))
        if expected_media != artifact.media_type:
            findings.append(
                VaultFinding(
                    kind="media-changed",
                    rel=rel,
                    detail=f"records {artifact.media_type}, extension table says {expected_media}",
                )
            )

    return findings
