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
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

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


def _is_pointer(path: Path) -> bool:
    """Whether *path* holds a Git-LFS pointer stub rather than the bytes it names."""
    try:
        with path.open("rb") as fh:
            return parse_pointer(fh.read(256)) is not None
    except OSError:
        return False


def cache_dir(settings: Settings | None = None) -> Path:
    """Where the yidam vault keeps content-addressed bytes on this machine.

    ``YIDAM_VAULT_CACHE``, else ``$XDG_CACHE_HOME/yidam/vault``, else ``~/.cache/yidam/vault`` —
    yidam's own resolution order, read through :func:`watermark.config.get_settings` rather than
    the environment so the two agree by construction rather than by coincidence.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    if settings.yidam_vault_cache:
        return Path(settings.yidam_vault_cache).expanduser()
    base = Path(settings.xdg_cache_home).expanduser() if settings.xdg_cache_home else None
    return (base or Path.home() / ".cache") / "yidam" / "vault"


def cache_path(cache: Path, sha256: str) -> Path:
    """``<cache>/sha256/<aa>/<64-hex>`` — the layout RFC-0023 fixes for the store and the cache."""
    return cache / "sha256" / sha256[:2] / sha256


class HydrateOutcome(BaseModel):
    """What hydration did, or would do, for one artifact."""

    model_config = ConfigDict(extra="forbid")

    # linked | copied | present | pointer | absent-from-cache | conflict
    action: str
    rel: str
    detail: str = ""


def _cache_address(path: Path) -> tuple[str, int] | None:
    """``(sha256, bytes)`` of a cache entry, hashing unconditionally.

    Deliberately **not** :func:`content_address`: that reads a Git-LFS pointer as the content it
    names, which is right for the working tree and exactly wrong here. The cache stores bytes, so
    a pointer sitting at a content address is one of the corruptions this is checking for — and
    the pointer-aware reader would report it as the very digest it is standing in for.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        size = path.stat().st_size
    except OSError:
        return None
    return (digest.hexdigest(), size)


def _copy_new(source: Path, target: Path) -> None:
    """Place a copy of *source* at *target* atomically, refusing to touch an existing file.

    Two ways a copy writes something wrong into a tree whose contents are evidence, and both are
    excluded here:

    * ``shutil.copyfile`` opens the destination ``"wb"``, which **truncates** what it finds;
    * a copy that dies part-way — a full disk, an unreadable cache entry, a killed process —
      leaves a **partial file under the real name**, which is a corrupt source byte wearing a
      valid one's identity, and the next run reports it as a conflict for a human to untangle.

    So the bytes land in a temporary sibling and the name is claimed from the *finished* file with
    ``os.link``, which raises ``FileExistsError`` rather than replacing. The temporary is removed
    on either outcome. Nothing partial is ever reachable under *target*: a process killed mid-copy
    leaves an orphan ``.vault-*.part`` beside it, not a truncated record.

    ``mkstemp`` rather than a name derived from the target's: several source filenames are long
    enough that a derived prefix could exceed the 255-byte limit, and uniqueness has to hold when
    two artifacts in one directory are placed at once.
    """
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".vault-", suffix=".part")
    tmp = Path(tmp_name)
    try:
        with open(fd, "wb") as dest, source.open("rb") as src:
            shutil.copyfileobj(src, dest)
        tmp.chmod(0o644)  # mkstemp creates 0600; os.link carries the mode to the target
        os.link(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def hydrate(
    data_dir: Path,
    *,
    rels: Iterable[str] | None = None,
    settings: Settings | None = None,
    check: bool = False,
) -> list[HydrateOutcome]:
    """Materialize vaulted bytes into the working tree under their **as-received** names.

    This exists because ``yidam vault materialize`` does not. Upstream writes
    ``.yidam/vault/<entry-slug>/<slug>-<hash8>.<ext-from-media_type>``, which is right for its
    question — *give a person a real file to open* — and wrong for this corpus, where the filename
    is evidence: three files carry no extension and several carry upper-case ones precisely because
    a source name is never "fixed" (see ``filename-map.yaml``). Measured on ``cli/v0.8.0``,
    ``1-12-26 minutes.docx`` materialized as ``multi-527ba1ba.bin``.

    So this hardlinks ``<cache>/sha256/<aa>/<hex>`` to ``data/<rel>``, falling back to a copy across
    devices. A hardlink is the point: the bytes are already on the disk once, and the corpus does
    not need a second copy of 3.6 GB to be readable.

    **It never overwrites a file whose bytes differ from the record.** A mismatch is reported as a
    ``conflict`` and left alone, in either mode. Hydration must not be able to become the thing
    that altered a source byte — that is the whole custody argument, and a tool that "fixes" a
    divergence by overwriting it destroys the evidence that there was one.

    Idempotent: an artifact already correct in place is ``present`` and untouched.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()
    cache = cache_dir(settings)
    # De-duplicated on both paths, because both could double-count one artifact: `--paths-from`
    # can name a rel twice (`data/x` and `./data/x` normalize to the same thing), and two
    # manifests can record it twice. Hydrating it twice reports it twice — inflating the counts a
    # caller gates on. `check` is what reports a doubly-recorded rel, and it reads the manifests
    # directly, so de-duplicating here cannot hide one.
    wanted = sorted(set(rels)) if rels is not None else recorded_rels(data_dir)
    by_rel = {a.rel: a for _, a in _iter_committed(data_dir)}

    outcomes: list[HydrateOutcome] = []
    for rel in wanted:
        artifact = by_rel.get(rel)
        if artifact is None:
            outcomes.append(
                HydrateOutcome(action="conflict", rel=rel, detail=f"named by no {MANIFEST_NAME}")
            )
            continue
        target = data_dir / rel
        address = content_address(target)
        # The pointer's own address, or None when what is in place is not a pointer. Carried as a
        # value rather than a bool so the unlink below can be gated on the same fact it was
        # established from.
        pointer_address = address if address is not None and _is_pointer(target) else None
        if pointer_address is not None:
            # ⚠️ A pointer hash-MATCHES the record, because an oid is the content's sha256 — which
            # is what makes the manifest derivable without the bytes, and what would make a naive
            # "does it match?" check read an unmaterialized stub as satisfied. It is not: nothing
            # can read it. Named separately so `--check` keeps the guard `bundle-freshness.yml`
            # has today, where a pointer parsed as data yields zero rows rather than an error.
            #
            # But *hash-matches* is the premise, and it has to be checked rather than assumed. A
            # pointer naming some OTHER digest is a divergence between two committed records —
            # the manifest and the pointer — and deleting it would resolve that divergence by
            # destroying half of it. Same refusal as bytes that disagree, in both modes.
            if pointer_address[0] != artifact.sha256:
                outcomes.append(
                    HydrateOutcome(
                        action="conflict",
                        rel=rel,
                        detail=(
                            f"pointer names {pointer_address[0][:12]}…, record says "
                            f"{artifact.sha256[:12]}… — left untouched"
                        ),
                    )
                )
                continue
            if check:
                outcomes.append(
                    HydrateOutcome(
                        action="pointer", rel=rel, detail="unresolved Git-LFS pointer, not bytes"
                    )
                )
                continue
        elif address is not None:
            if address[0] == artifact.sha256:
                outcomes.append(HydrateOutcome(action="present", rel=rel))
            else:
                outcomes.append(
                    HydrateOutcome(
                        action="conflict",
                        rel=rel,
                        detail=(
                            f"in place with {address[0][:12]}…, record says "
                            f"{artifact.sha256[:12]}… — left untouched"
                        ),
                    )
                )
            continue
        # ⚠️ The cache is resolved and VERIFIED before a pointer is unlinked, not after. Deleting
        # the stub first and discovering the cache empty left the tree with neither the bytes nor
        # the record of which bytes belong there — a command whose stated invariant is that a
        # disagreement is reported and nothing is written, removing a file on its way to saying
        # `absent-from-cache`.
        source = cache_path(cache, artifact.sha256)
        if not source.is_file():
            outcomes.append(
                HydrateOutcome(
                    action="absent-from-cache",
                    rel=rel,
                    detail=f"{artifact.sha256[:12]}… not cached — `yidam vault pull` fetches it",
                )
            )
            continue
        # The cache path ASSERTS the digest; it does not establish it. A corrupt or substituted
        # entry would otherwise be hardlinked into `data/**` and reported `linked` — hydration
        # becoming the thing that wrote a wrong source byte, which is the one outcome this
        # module exists to make impossible. One hash of what is about to be written anyway.
        cached = _cache_address(source)
        if cached != (artifact.sha256, artifact.bytes):
            held = "unreadable" if cached is None else f"{cached[0][:12]}… / {cached[1]} B"
            outcomes.append(
                HydrateOutcome(
                    action="conflict",
                    rel=rel,
                    detail=(
                        f"cache entry for {artifact.sha256[:12]}… holds {held} — not materialized"
                    ),
                )
            )
            continue
        if check:
            outcomes.append(HydrateOutcome(action="linked", rel=rel, detail="would link"))
            continue
        if pointer_address is not None:
            # Safe now, and only now: the bytes the oid names are cached and verified.
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except FileExistsError:
            # `address is None` does not prove the target is absent: `content_address` also
            # answers None for a file it cannot READ. Falling through to a copy here would
            # truncate whatever is actually there — the overwrite this module refuses.
            outcomes.append(
                HydrateOutcome(
                    action="conflict",
                    rel=rel,
                    detail="a file is at the target that could not be read — left untouched",
                )
            )
        except OSError:
            # A cross-device cache is the documented case; a filesystem without hardlinks and an
            # exhausted link count reach here too, and all three want the same fallback. The copy
            # is EXCLUSIVE, so the narrowing that matters is at the destination, not the errno.
            try:
                _copy_new(source, target)
            except FileExistsError:
                outcomes.append(
                    HydrateOutcome(
                        action="conflict",
                        rel=rel,
                        detail="a file is at the target that could not be read — left untouched",
                    )
                )
            except OSError as exc:
                # A target filesystem with no hardlinks at all reaches here, since the atomic
                # claim in `_copy_new` is itself a link. Reported rather than raised: one
                # unplaceable artifact must not abort the other 3,661, and nothing was written.
                outcomes.append(
                    HydrateOutcome(
                        action="conflict", rel=rel, detail=f"could not place the bytes: {exc}"
                    )
                )
            else:
                outcomes.append(HydrateOutcome(action="copied", rel=rel, detail="cross-device"))
        else:
            outcomes.append(HydrateOutcome(action="linked", rel=rel))
    return outcomes


def recorded_rels(data_dir: Path) -> list[str]:
    """Every rel the committed manifests name — the hydration set, and the post-untrack inventory.

    Distinct from :func:`tracked_rels`, which asks Git-LFS: after #2147 that returns nothing and
    this is the only answer left. Which is the point of committing the record.

    **De-duplicated.** Two manifests naming one rel is a real state — :func:`check` reports it as
    ``duplicated``, reading the manifests directly so this cannot hide it — but it is still ONE
    artifact. Returning it twice hydrated it twice (``1 linked`` then ``1 present`` for a single
    file) and double-counted it in the post-untrack inventory this is also the answer for.
    """
    return sorted({artifact.rel for _, artifact in _iter_committed(data_dir)})


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
