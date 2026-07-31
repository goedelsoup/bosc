"""Committed plain-text sidecars for the corpus' legacy binary formats (#1757).

``.doc`` / ``.dot`` / ``.xls`` / ``.rtf`` are OLE2 and RTF containers with no in-process reader,
so the 600-odd of them the batch-3 sanitary production landed (epic #1744) are invisible to every
retrieval path. This module makes them readable the only honest way available: convert each one
**once**, out of band, through LibreOffice, and commit the resulting text next to the corpus so
the index — and a human reading the repo — can see what the file says.

**The `-text` tree.** A sidecar never lands inside the as-received tree; the production's custody
manifest asserts that tree is byte- and layout-identical to what the county produced, and an
interleaved derived file would break that claim. Instead each source directory gets a **sibling**
named with a ``-text`` suffix, mirroring the source layout one-for-one::

    data/documents/legal/…/prr-production-2026-07-24-sanitary/14/…/Shawnee Oaks Letter.DOC
    data/documents/legal/…/prr-production-2026-07-24-sanitary-text/14/…/Shawnee Oaks Letter.DOC.txt

The sidecar keeps the source's **full** as-received name, extension included, so the pairing is
unambiguous even where two files differ only by extension, and survives the corpus' upper-case
extensions. The convention is self-describing: a directory under ``data/documents/`` whose name
ends in ``-text`` and whose de-suffixed sibling exists **is** a sidecar tree, which is how
:func:`sidecar_source_rel` lets the readers attribute a sidecar's text back to the record it came
from — a citation names the ``.DOC``, never the derived ``.txt``.

**Derived, and marked as such.** Every tree carries a ``text-sidecars.yaml`` manifest (the
``derived_files`` precedent of ``data/documents/aedg/PRR-01-bundle.ocr.pdf.index.yaml``) recording,
per source: its sha256, the converter that read it, and the character count — or, when the
conversion yielded nothing, an explicit note. That makes the sidecars *regenerable* (never
hand-edited: the next run reverts an edit) and *falsifiable* (:func:`check` re-hashes every source
and reports drift, so a sidecar can't quietly outlive the bytes it claims to transcribe).

**Chain of custody.** Nothing here reads or writes a byte under a source directory; the conversion
input is opened read-only and every write lands under the ``-text`` sibling. A source that is an
unresolved Git-LFS pointer is refused outright rather than "converted" into a transcript of the
pointer stub.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.documents.office import (
    CALC_SUFFIXES,
    SIDECAR_SOURCE_SUFFIXES,
    detect_suffix,
    is_lfs_pointer,
    xlsx_text,
)
from watermark.logging import get_logger

log = get_logger(__name__)

SIDECAR_DIR_SUFFIX = "-text"
SIDECAR_FILE_SUFFIX = ".txt"
MANIFEST_NAME = "text-sidecars.yaml"
README_NAME = "README.md"

# Files a sidecar tree carries that are *about* the sidecars rather than sidecars themselves.
_TREE_METADATA = frozenset({MANIFEST_NAME, README_NAME})

# LibreOffice's "Text (encoded)" filter, pinned to UTF-8 — the default guesses the system
# encoding, which would mangle the production's cp1252 smart quotes and section marks.
_WRITER_FILTER = "txt:Text (encoded):UTF8"
_CALC_FILTER = "xlsx"

# One soffice invocation converts a whole batch, so the ~2s process start is paid once per batch
# rather than per file (600 documents: ~45s instead of ~20min). Bounded so a failure mid-batch
# costs a re-run of 100 files, not of everything.
_BATCH = 100
_TIMEOUT_S = 900

_BLANK_RUN = re.compile(r"\n{3,}")


# --- the -text tree convention ------------------------------------------------------------------
def sidecar_tree_rel(source_root: str | PurePosixPath) -> PurePosixPath:
    """The ``-text`` sibling of the source directory *source_root* (both ``documents_dir``-rel)."""
    root = PurePosixPath(source_root)
    return root.with_name(root.name + SIDECAR_DIR_SUFFIX)


def sidecar_rel(
    source_rel: str | PurePosixPath, *, source_root: str | PurePosixPath
) -> PurePosixPath:
    """Where the sidecar for *source_rel* lives, given the tree's *source_root*."""
    rel = PurePosixPath(source_rel)
    within = rel.relative_to(PurePosixPath(source_root))
    return sidecar_tree_rel(source_root) / within.with_name(within.name + SIDECAR_FILE_SUFFIX)


def _tree_split(
    rel: PurePosixPath, documents_dir: Path
) -> tuple[PurePosixPath, PurePosixPath] | None:
    """``(source_root, within)`` when *rel* sits inside a sidecar tree, else ``None``.

    A path segment qualifies only when its de-suffixed sibling is a real directory, so an
    as-received folder that merely happens to end in ``-text`` is never mistaken for one.
    """
    for i, part in enumerate(rel.parts[:-1]):
        if not part.endswith(SIDECAR_DIR_SUFFIX) or part == SIDECAR_DIR_SUFFIX:
            continue
        source_root = PurePosixPath(*rel.parts[:i], part[: -len(SIDECAR_DIR_SUFFIX)])
        if (documents_dir / source_root).is_dir():
            return (source_root, PurePosixPath(*rel.parts[i + 1 :]))
    return None


def in_sidecar_tree(rel: str | PurePosixPath, documents_dir: Path) -> bool:
    """Whether *rel* (``documents_dir``-relative) is derived sidecar content, not source bytes."""
    return _tree_split(PurePosixPath(rel), documents_dir) is not None


def sidecar_source_rel(rel: str | PurePosixPath, documents_dir: Path) -> PurePosixPath | None:
    """The source document a sidecar transcribes, or ``None`` if *rel* isn't a sidecar.

    ``None`` covers both "not in a sidecar tree at all" and "in one, but is the tree's own
    manifest/README" — neither should be indexed as a document's text.
    """
    path = PurePosixPath(rel)
    split = _tree_split(path, documents_dir)
    if split is None:
        return None
    source_root, within = split
    if within.name in _TREE_METADATA or not within.name.endswith(SIDECAR_FILE_SUFFIX):
        return None
    source = source_root / within.with_name(within.name[: -len(SIDECAR_FILE_SUFFIX)])
    return source if (documents_dir / source).is_file() else None


# --- the committed manifest ---------------------------------------------------------------------
class SidecarEntry(BaseModel):
    """One source document and the text sidecar derived from it (or why there isn't one)."""

    model_config = ConfigDict(extra="forbid")

    source: str  # data/documents-relative path of the source document
    sidecar: str | None  # data/documents-relative path of the .txt, null when no text was produced
    source_sha256: str  # ties the sidecar to exact source bytes; re-checked by check()
    source_bytes: int
    chars: int
    converter: str
    note: str | None = None


class SidecarMeta(BaseModel):
    """Provenance for one ``-text`` tree."""

    model_config = ConfigDict(extra="forbid")

    source_dir: str
    sidecar_dir: str
    policy: str
    converter_version: str
    generated_at: str
    generated_by: str
    counts: dict[str, int]


class SidecarManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: SidecarMeta
    files: list[SidecarEntry]


_POLICY = (
    "derived, not evidence: every .txt here is a machine transcription of the source file named "
    "in `source`, produced by the converter in meta.converter_version and regenerable with "
    "`watermark text-sidecars <source-dir>`. Never hand-edit one — the next run reverts it; a "
    "correction belongs in a reviewed artifact under data/extracted/. The source bytes are "
    "untouched and remain the citable record."
)

_README = """\
# {sidecar_dir}

**Derived text sidecars — not source evidence.**

Plain-text transcriptions of the legacy binary documents (`.doc` / `.dot` / `.xls` / `.rtf`) in
the sibling [`{source_name}/`](../{source_name}/), which have no in-process text reader and were
therefore unsearchable. This tree mirrors that one file-for-file: a source `X.DOC` has its text
at the same relative path here, named `X.DOC.txt`.

The sidecars exist so the production is retrievable ([#1757]). They are **regenerable**:

```sh
watermark text-sidecars {source_dir}          # rewrite this tree
watermark text-sidecars {source_dir} --check  # verify it still matches the source bytes
```

`{manifest}` records, per source file, its sha256, the converter that read it, and the character
count — or an explicit note where the conversion produced no text. Because the manifest pins the
source hash, a sidecar cannot quietly outlive the bytes it claims to transcribe.

Rules:

- **Never hand-edit a sidecar.** The next run reverts it. A reviewed, cited correction belongs in
  `data/extracted/`, not here.
- **Cite the source, never the sidecar.** The `.DOC` is the record; this is a reading aid.
- The transcription is mechanical and unreviewed. Tables, headers, and footers may be flattened
  or reordered; verify against the source before quoting.
"""


def manifest_path(documents_dir: Path, source_root: str | PurePosixPath) -> Path:
    return documents_dir / sidecar_tree_rel(source_root) / MANIFEST_NAME


def load_manifest(documents_dir: Path, source_root: str | PurePosixPath) -> SidecarManifest | None:
    path = manifest_path(documents_dir, source_root)
    if not path.is_file():
        return None
    return SidecarManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# --- conversion -----------------------------------------------------------------------------------
class ConverterUnavailableError(RuntimeError):
    """LibreOffice (``soffice``) isn't on PATH, so legacy formats can't be converted."""


def _soffice() -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if exe is None:
        raise ConverterUnavailableError(
            "LibreOffice is required to convert legacy Office formats; install it "
            "(`brew install --cask libreoffice`) and re-run"
        )
    return exe


def converter_version(exe: str | None = None) -> str:
    """The converter's self-reported version, recorded in the manifest for reproducibility."""
    try:
        out = subprocess.run(
            [exe or _soffice(), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else "unknown"


def _convert_batch(exe: str, sources: Sequence[Path], target: str, outdir: Path) -> None:
    """Run one ``soffice --convert-to`` over *sources*, writing into *outdir*.

    A private ``UserInstallation`` profile keeps the run from colliding with (or corrupting) an
    interactive LibreOffice the operator may have open — soffice refuses a second instance on a
    shared profile. A non-zero exit is logged, not raised: the caller decides per file, from
    whether an output landed, and records the misses in the manifest.
    """
    with tempfile.TemporaryDirectory(prefix="watermark-lo-") as profile:
        try:
            out = subprocess.run(
                [
                    exe,
                    f"-env:UserInstallation=file://{profile}",
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    target,
                    "--outdir",
                    str(outdir),
                    *(str(p) for p in sources),
                ],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            log.warning("text_sidecars.convert_timeout", target=target, files=len(sources))
            return
    if out.returncode != 0:
        log.warning(
            "text_sidecars.convert_nonzero",
            target=target,
            files=len(sources),
            returncode=out.returncode,
            stderr=out.stderr.strip()[:400],
        )


def _normalize(text: str) -> str:
    """Trim the converter's artifacts: the UTF-8 BOM, CRLF, trailing spaces, blank-line runs."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _BLANK_RUN.sub("\n\n", text).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_sidecar_sources(source_dir: Path) -> Iterator[tuple[Path, str]]:
    """``(path, effective_suffix)`` for every legacy binary document under *source_dir*."""
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = detect_suffix(path)
        if suffix in SIDECAR_SOURCE_SUFFIXES:
            yield (path, suffix)


class SidecarReport(BaseModel):
    """Outcome of one ``watermark text-sidecars`` run."""

    model_config = ConfigDict(extra="forbid")

    source_dir: str
    sidecar_dir: str
    written: int
    empty: int
    failed: int
    skipped_pointers: int
    pruned: list[str]


def _extract_batch(
    exe: str,
    staged: list[tuple[Path, Path, str]],
    target: str,
    render: str,
    workdir: Path,
) -> dict[Path, str]:
    """Convert the staged ``(source, staged_copy, out_stem)`` triples; return source → text."""
    outdir = workdir / f"out-{render}"
    outdir.mkdir(parents=True, exist_ok=True)
    texts: dict[Path, str] = {}
    for start in range(0, len(staged), _BATCH):
        window = staged[start : start + _BATCH]
        _convert_batch(exe, [copy for _, copy, _ in window], target, outdir)
        for source, _, stem in window:
            produced = outdir / f"{stem}.{target.split(':')[0]}"
            if not produced.is_file():
                continue
            if render == "writer":
                texts[source] = _normalize(produced.read_text(encoding="utf-8", errors="replace"))
            else:
                texts[source] = _normalize(xlsx_text(produced))
    return texts


def generate(
    documents_dir: Path,
    source_root: str | PurePosixPath,
    *,
    now: datetime | None = None,
) -> SidecarReport:
    """Rewrite the ``-text`` sidecar tree for *source_root* and its manifest.

    Converts every legacy binary document under ``documents_dir / source_root``, writes one
    ``.txt`` per document that yielded text, prunes sidecars whose source is gone, and records the
    whole set — including the empty and failed conversions — in ``text-sidecars.yaml``.
    """
    source_root = PurePosixPath(source_root)
    source_dir = documents_dir / source_root
    if not source_dir.is_dir():
        raise FileNotFoundError(f"no such source directory: {source_dir}")
    tree_rel = sidecar_tree_rel(source_root)
    tree_dir = documents_dir / tree_rel

    exe = _soffice()
    sources = list(iter_sidecar_sources(source_dir))

    entries: list[SidecarEntry] = []
    pointers = {path for path, _ in sources if is_lfs_pointer(path)}
    convertible = [(path, suffix) for path, suffix in sources if path not in pointers]
    if pointers:
        log.warning("text_sidecars.lfs_pointers", count=len(pointers), source_dir=str(source_root))

    with tempfile.TemporaryDirectory(prefix="watermark-sidecars-") as tmp:
        workdir = Path(tmp)
        stage = workdir / "in"
        stage.mkdir()
        # Stage under sequential ASCII names: the corpus' as-received filenames carry '&', commas,
        # and duplicate basenames across directories, any of which would collide or confuse the
        # converter's flat --outdir. The index maps each output back to its source.
        by_render: dict[str, list[tuple[Path, Path, str]]] = {"writer": [], "calc": []}
        for i, (path, suffix) in enumerate(convertible):
            stem = f"{i:05d}"
            copy = stage / f"{stem}{suffix}"
            shutil.copyfile(path, copy)
            render = "calc" if suffix in CALC_SUFFIXES else "writer"
            by_render[render].append((path, copy, stem))

        texts: dict[Path, str] = {}
        if by_render["writer"]:
            texts |= _extract_batch(exe, by_render["writer"], _WRITER_FILTER, "writer", workdir)
        if by_render["calc"]:
            texts |= _extract_batch(exe, by_render["calc"], _CALC_FILTER, "calc", workdir)

    written = empty = failed = 0
    keep: set[Path] = set()
    for path, suffix in sources:
        rel = PurePosixPath(path.relative_to(documents_dir).as_posix())
        converter = "libreoffice-calc+openpyxl" if suffix in CALC_SUFFIXES else "libreoffice-writer"
        if path in pointers:
            # The hash is of the pointer stub, not the record — check() knows to skip it, and the
            # note keeps a pointer-only run from reading as a clean one.
            entries.append(
                SidecarEntry(
                    source=str(rel),
                    sidecar=None,
                    source_sha256=_sha256(path),
                    source_bytes=path.stat().st_size,
                    chars=0,
                    converter=converter,
                    note="skipped: unresolved Git-LFS pointer — run `git lfs pull` and re-run",
                )
            )
            continue
        text = texts.get(path)
        note: str | None = None
        out_rel: str | None = None
        if text is None:
            failed += 1
            note = "conversion failed: the converter produced no output for this file"
        elif not text:
            empty += 1
            note = "no text: the document body is empty or image-only"
        else:
            written += 1
            target_rel = sidecar_rel(rel, source_root=source_root)
            target = documents_dir / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text + "\n", encoding="utf-8")
            keep.add(target)
            out_rel = str(target_rel)
        entries.append(
            SidecarEntry(
                source=str(rel),
                sidecar=out_rel,
                source_sha256=_sha256(path),
                source_bytes=path.stat().st_size,
                chars=len(text or ""),
                converter=converter,
                note=note,
            )
        )

    pruned = _prune(tree_dir, keep)
    entries.sort(key=lambda e: e.source)
    meta = SidecarMeta(
        source_dir=str(source_root),
        sidecar_dir=str(tree_rel),
        policy=_POLICY,
        converter_version=converter_version(exe),
        generated_at=(now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        generated_by="watermark text-sidecars",
        counts={
            "sources": len(sources),
            "sidecars": written,
            "no_text": empty,
            "failed": failed,
            "lfs_pointers": len(pointers),
        },
    )
    tree_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest(tree_dir / MANIFEST_NAME, SidecarManifest(meta=meta, files=entries))
    (tree_dir / README_NAME).write_text(
        _README.format(
            sidecar_dir=tree_rel.name,
            source_name=source_root.name,
            source_dir=source_root,
            manifest=MANIFEST_NAME,
        ),
        encoding="utf-8",
    )
    log.info(
        "text_sidecars.generated",
        source_dir=str(source_root),
        written=written,
        empty=empty,
        failed=failed,
        pruned=len(pruned),
    )
    return SidecarReport(
        source_dir=str(source_root),
        sidecar_dir=str(tree_rel),
        written=written,
        empty=empty,
        failed=failed,
        skipped_pointers=len(pointers),
        pruned=sorted(pruned),
    )


def _write_manifest(path: Path, manifest: SidecarManifest) -> None:
    payload = manifest.model_dump(mode="json", exclude_none=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _prune(tree_dir: Path, keep: set[Path]) -> list[str]:
    """Delete sidecars this run didn't write, so a removed source can't leave a stale transcript."""
    if not tree_dir.is_dir():
        return []
    removed: list[str] = []
    for path in sorted(tree_dir.rglob(f"*{SIDECAR_FILE_SUFFIX}")):
        if path.is_file() and path not in keep:
            path.unlink()
            removed.append(path.relative_to(tree_dir).as_posix())
    for path in sorted(tree_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed


# --- verification ---------------------------------------------------------------------------------
class SidecarFinding(BaseModel):
    """One way the committed tree and the source directory disagree."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # missing-manifest | source-changed | source-gone | unmanifested-source | orphan
    path: str
    detail: str


def check(documents_dir: Path, source_root: str | PurePosixPath) -> list[SidecarFinding]:
    """Verify the committed sidecar tree still describes the source directory it claims to.

    Re-hashes every source in the manifest, and cross-checks both directions — a source that
    changed under a sidecar, one that disappeared, one that was added without a regeneration, and
    a sidecar file no manifest entry accounts for. An empty list means the tree is current.
    """
    source_root = PurePosixPath(source_root)
    manifest = load_manifest(documents_dir, source_root)
    tree_rel = sidecar_tree_rel(source_root)
    if manifest is None:
        return [
            SidecarFinding(
                kind="missing-manifest",
                path=str(tree_rel / MANIFEST_NAME),
                detail="no sidecar manifest — run `watermark text-sidecars <source-dir>`",
            )
        ]

    findings: list[SidecarFinding] = []
    manifested = {e.source for e in manifest.files}
    expected: set[Path] = set()

    for entry in manifest.files:
        # A manifested sidecar is accounted for whatever its source turns out to be — otherwise a
        # source that vanished, or that is a pointer on this checkout, would double-report as an
        # orphaned sidecar on top of the finding that actually explains it.
        if entry.sidecar:
            expected.add(documents_dir / entry.sidecar)
        source = documents_dir / entry.source
        if not source.is_file():
            findings.append(
                SidecarFinding(
                    kind="source-gone",
                    path=entry.source,
                    detail="manifested source no longer exists; regenerate to prune its sidecar",
                )
            )
            continue
        if is_lfs_pointer(source):
            continue  # can't hash real bytes on an LFS-less checkout; not drift
        actual = _sha256(source)
        if actual != entry.source_sha256:
            findings.append(
                SidecarFinding(
                    kind="source-changed",
                    path=entry.source,
                    detail=f"sha256 {actual[:12]}… != manifested {entry.source_sha256[:12]}…",
                )
            )

    for path, _suffix in iter_sidecar_sources(documents_dir / source_root):
        rel = path.relative_to(documents_dir).as_posix()
        if rel not in manifested:
            findings.append(
                SidecarFinding(
                    kind="unmanifested-source",
                    path=rel,
                    detail="legacy document with no manifest entry; regenerate",
                )
            )

    tree_dir = documents_dir / tree_rel
    if tree_dir.is_dir():
        for path in sorted(tree_dir.rglob(f"*{SIDECAR_FILE_SUFFIX}")):
            if path.is_file() and path not in expected:
                findings.append(
                    SidecarFinding(
                        kind="orphan",
                        path=path.relative_to(documents_dir).as_posix(),
                        detail="sidecar file no manifest entry accounts for",
                    )
                )
    return findings
