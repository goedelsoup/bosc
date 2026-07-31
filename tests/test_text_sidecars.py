"""The committed ``-text`` sidecar trees for legacy binary formats (#1757).

Hermetic: the LibreOffice hop is stubbed at :func:`watermark.text_sidecars._extract_batch`, so
the tree layout, manifest, pruning, and drift checks are exercised without a converter on PATH.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
import yaml

from watermark import text_sidecars
from watermark.text_sidecars import (
    ConverterUnavailableError,
    SidecarGenerationError,
    check,
    generate,
    in_sidecar_tree,
    load_manifest,
    sidecar_rel,
    sidecar_source_rel,
    sidecar_tree_rel,
)

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

PROD = "legal/prr-mandamus/prr-production-2026-07-24-sanitary"


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """A miniature documents tree: two legacy documents and one PDF that isn't one."""
    root = tmp_path / "documents"
    source = root / PROD
    (source / "14" / "Correspondence").mkdir(parents=True)
    (source / "14" / "Correspondence" / "Shawnee Oaks Letter.DOC").write_bytes(_OLE2 + b"letter")
    (source / "14" / "EPA - Amort.xls").write_bytes(_OLE2 + b"sheet")
    (source / "14" / "CERTIFICATE.pdf").write_bytes(b"%PDF-1.4\n")
    return root


def _stub_converter(monkeypatch: pytest.MonkeyPatch, texts: dict[str, str]) -> None:
    """Replace the LibreOffice hop: map each staged source's *name* to canned text."""
    monkeypatch.setattr(text_sidecars, "_soffice", lambda: "/usr/bin/true")
    monkeypatch.setattr(
        text_sidecars, "converter_version", lambda exe=None: "LibreOffice 26.2 test"
    )
    monkeypatch.setattr(
        text_sidecars,
        "_extract_batch",
        lambda exe, staged, target, render, workdir: {
            src: texts[src.name] for src, _copy, _stem in staged if src.name in texts
        },
    )


# --- the tree convention -------------------------------------------------------------------------
def test_sidecar_tree_is_a_sibling_of_the_source_directory() -> None:
    assert str(sidecar_tree_rel(PROD)) == f"{PROD}-text"


def test_sidecar_keeps_the_source_extension_in_its_name() -> None:
    # 'X.DOC' and 'X.pdf' in one folder must not collide, and the corpus' upper-case as-received
    # extensions have to survive — so the sidecar name is the WHOLE source name plus '.txt'.
    rel = sidecar_rel(f"{PROD}/14/Shawnee Oaks Letter.DOC", source_root=PROD)
    assert str(rel) == f"{PROD}-text/14/Shawnee Oaks Letter.DOC.txt"


def test_a_directory_ending_in_text_is_not_a_sidecar_tree_without_a_source_sibling(
    tmp_path: Path,
) -> None:
    # An as-received folder may legitimately be named '…-text'; only a de-suffixed sibling
    # DIRECTORY makes it a sidecar tree.
    root = tmp_path / "documents"
    (root / "legal" / "exhibit-text").mkdir(parents=True)
    (root / "legal" / "exhibit-text" / "note.txt").write_text("body", encoding="utf-8")
    assert not in_sidecar_tree("legal/exhibit-text/note.txt", root)
    assert sidecar_source_rel("legal/exhibit-text/note.txt", root) is None


def test_sidecar_source_rel_resolves_back_to_the_record(docs: Path) -> None:
    tree = docs / f"{PROD}-text" / "14" / "Correspondence"
    tree.mkdir(parents=True)
    (tree / "Shawnee Oaks Letter.DOC.txt").write_text("text", encoding="utf-8")
    rel = f"{PROD}-text/14/Correspondence/Shawnee Oaks Letter.DOC.txt"
    assert in_sidecar_tree(rel, docs)
    assert sidecar_source_rel(rel, docs) == PurePosixPath(
        f"{PROD}/14/Correspondence/Shawnee Oaks Letter.DOC"
    )


def test_the_trees_own_metadata_is_not_a_sidecar(docs: Path) -> None:
    tree = docs / f"{PROD}-text"
    tree.mkdir(parents=True)
    (tree / "text-sidecars.yaml").write_text("meta: {}", encoding="utf-8")
    (tree / "README.md").write_text("# derived", encoding="utf-8")
    for name in ("text-sidecars.yaml", "README.md"):
        rel = f"{PROD}-text/{name}"
        assert in_sidecar_tree(rel, docs)  # inside the tree...
        assert sidecar_source_rel(rel, docs) is None  # ...but transcribes nothing


def test_a_sidecar_whose_source_vanished_resolves_to_nothing(docs: Path) -> None:
    tree = docs / f"{PROD}-text" / "14"
    tree.mkdir(parents=True)
    (tree / "Deleted.doc.txt").write_text("stale", encoding="utf-8")
    assert sidecar_source_rel(f"{PROD}-text/14/Deleted.doc.txt", docs) is None


# --- converter artifacts -------------------------------------------------------------------------
def test_a_filename_field_resolves_to_the_source_not_our_staging_copy() -> None:
    # Writer resolves Word's FILENAME field at export time, against the file it was handed — so
    # 255 of the sanitary production's 634 documents came back naming a per-run temp path. That is
    # both wrong (our scratch dir, not anything the county wrote) and non-deterministic, which
    # would churn every regeneration and defeat the manifest's sidecar hashes.
    staged = Path("/tmp/watermark-sidecars-ab12/in/00016.doc")
    text = "SMK\n/tmp/watermark-sidecars-ab12/in/00016.doc\n"
    assert (
        text_sidecars._restore_source_name(
            text, staged=staged, source_name="Cover Letter for Findings and Orders.doc"
        )
        == "SMK\nCover Letter for Findings and Orders.doc\n"
    )


def test_a_bare_staged_filename_is_restored_too() -> None:
    staged = Path("/tmp/watermark-sidecars-ab12/in/00016.doc")
    got = text_sidecars._restore_source_name(
        "Document: 00016.doc", staged=staged, source_name="Shawnee Oaks Letter.DOC"
    )
    assert got == "Document: Shawnee Oaks Letter.DOC"


# --- generation ----------------------------------------------------------------------------------
def test_generate_writes_a_mirrored_tree_a_manifest_and_a_readme(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(
        monkeypatch,
        {
            "Shawnee Oaks Letter.DOC": "Dear Isabel:\n\nretainage account",
            "EPA - Amort.xls": "### 1\nPrincipal\t100",
        },
    )
    report = generate(docs, PROD)

    assert (report.written, report.empty, report.failed) == (2, 0, 0)
    tree = docs / f"{PROD}-text"
    assert (tree / "14" / "Correspondence" / "Shawnee Oaks Letter.DOC.txt").read_text(
        encoding="utf-8"
    ) == "Dear Isabel:\n\nretainage account\n"
    assert (tree / "14" / "EPA - Amort.xls.txt").is_file()
    assert "derived" in (tree / "README.md").read_text(encoding="utf-8").lower()
    # The PDF is not a legacy binary — it is read directly and gets no sidecar.
    assert not (tree / "14" / "CERTIFICATE.pdf.txt").exists()

    manifest = load_manifest(docs, PROD)
    assert manifest is not None
    assert manifest.meta.counts == {
        "sources": 2,
        "sidecars": 2,
        "no_text": 0,
        "failed": 0,
        "lfs_pointers": 0,
    }
    converters = {e.source.rsplit(".", 1)[1]: e.converter for e in manifest.files}
    assert converters == {"DOC": "libreoffice-writer", "xls": "libreoffice-calc+openpyxl"}
    assert all(len(e.source_sha256) == 64 for e in manifest.files)


def test_generate_records_an_empty_conversion_instead_of_writing_a_blank_sidecar(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A signed order scanned into a .doc has no text body. The gap belongs in the manifest, not
    # in a zero-byte file that reads as a successful transcription.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "", "EPA - Amort.xls": "rows"})
    report = generate(docs, PROD)

    assert (report.written, report.empty) == (1, 1)
    assert not (docs / f"{PROD}-text" / "14" / "Correspondence").exists()
    manifest = load_manifest(docs, PROD)
    assert manifest is not None
    empty = next(e for e in manifest.files if e.source.endswith(".DOC"))
    assert empty.sidecar is None
    assert empty.chars == 0
    assert empty.note is not None and "no text" in empty.note


def test_generate_records_a_failed_conversion(docs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_converter(monkeypatch, {"EPA - Amort.xls": "rows"})  # the .DOC produced no output at all
    report = generate(docs, PROD)

    assert (report.written, report.failed) == (1, 1)
    manifest = load_manifest(docs, PROD)
    assert manifest is not None
    failed = next(e for e in manifest.files if e.source.endswith(".DOC"))
    assert failed.note is not None and "failed" in failed.note


def test_generate_skips_an_unresolved_lfs_pointer_rather_than_transcribing_the_stub(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointer = docs / PROD / "14" / "Correspondence" / "Shawnee Oaks Letter.DOC"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:x\n", encoding="utf-8"
    )
    _stub_converter(monkeypatch, {"EPA - Amort.xls": "rows"})

    report = generate(docs, PROD)
    assert report.skipped_pointers == 1
    manifest = load_manifest(docs, PROD)
    assert manifest is not None
    entry = next(e for e in manifest.files if e.source.endswith(".DOC"))
    assert entry.sidecar is None
    assert entry.note is not None and "Git-LFS" in entry.note


def test_regenerating_prunes_a_sidecar_whose_source_is_gone(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    stale = docs / f"{PROD}-text" / "14" / "Correspondence" / "Shawnee Oaks Letter.DOC.txt"
    assert stale.is_file()

    (docs / PROD / "14" / "Correspondence" / "Shawnee Oaks Letter.DOC").unlink()
    report = generate(docs, PROD)

    assert not stale.exists()
    assert report.pruned == ["14/Correspondence/Shawnee Oaks Letter.DOC.txt"]
    assert not stale.parent.exists()  # the emptied directory goes too


def test_generate_is_deterministic_apart_from_its_timestamp(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    first = (docs / f"{PROD}-text" / "text-sidecars.yaml").read_text(encoding="utf-8")
    generate(docs, PROD)
    second = (docs / f"{PROD}-text" / "text-sidecars.yaml").read_text(encoding="utf-8")

    strip = lambda t: [ln for ln in t.splitlines() if "generated_at" not in ln]  # noqa: E731
    assert strip(first) == strip(second)


def test_generate_refuses_to_prune_when_it_converted_nothing(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A broken LibreOffice must not read as "the corpus has nothing to say" and delete the whole
    # committed tree, then rewrite the manifest to agree with itself.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    sidecar = docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt"
    manifest_before = (docs / f"{PROD}-text" / "text-sidecars.yaml").read_bytes()

    _stub_converter(monkeypatch, {})  # the converter now produces no output for anything
    with pytest.raises(SidecarGenerationError):
        generate(docs, PROD)

    assert sidecar.is_file()
    assert (docs / f"{PROD}-text" / "text-sidecars.yaml").read_bytes() == manifest_before


def test_generate_refuses_a_pointer_only_run(docs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Same protection for the other way a run converts nothing: a checkout without `git lfs pull`.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)

    for name in ("14/Correspondence/Shawnee Oaks Letter.DOC", "14/EPA - Amort.xls"):
        (docs / PROD / name).write_text(
            "version https://git-lfs.github.com/spec/v1\noid sha256:x\n", encoding="utf-8"
        )
    with pytest.raises(SidecarGenerationError):
        generate(docs, PROD)

    assert (docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt").is_file()


def test_generate_allows_a_directory_whose_documents_are_all_image_only(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No failures and no pointers: the converter worked and the documents really are scans. That
    # is a real outcome and must still write its (empty) manifest.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "", "EPA - Amort.xls": ""})
    report = generate(docs, PROD)
    assert (report.written, report.empty, report.failed) == (0, 2, 0)


def test_generate_refuses_a_missing_source_directory(docs: Path) -> None:
    with pytest.raises(FileNotFoundError):
        generate(docs, "legal/no-such-production")


def test_generate_reports_a_missing_converter(docs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_sidecars.shutil, "which", lambda _name: None)
    with pytest.raises(ConverterUnavailableError):
        generate(docs, PROD)


# --- verification --------------------------------------------------------------------------------
def test_check_passes_on_a_freshly_generated_tree(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    assert check(docs, PROD) == []


def test_check_reports_a_tree_that_was_never_generated(docs: Path) -> None:
    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["missing-manifest"]


def test_check_catches_a_source_edited_under_its_sidecar(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The whole point of pinning the source sha256: a sidecar must not outlive the bytes it
    # claims to transcribe.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / PROD / "14" / "EPA - Amort.xls").write_bytes(_OLE2 + b"revised")

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["source-changed"]
    assert findings[0].path.endswith("EPA - Amort.xls")


def test_check_catches_a_source_added_since_the_last_run(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / PROD / "14" / "New Resolution.doc").write_bytes(_OLE2 + b"new")

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["unmanifested-source"]


def test_check_reports_a_removed_source_once_not_twice(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `source-gone` already explains the leftover .txt; also calling it an orphan would double-
    # report one problem.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / PROD / "14" / "EPA - Amort.xls").unlink()

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["source-gone"]
    assert findings[0].path.endswith("EPA - Amort.xls")


def test_check_catches_a_deleted_sidecar(docs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt").unlink()

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["sidecar-missing"]
    assert findings[0].path.endswith("EPA - Amort.xls.txt")


def test_check_catches_a_hand_edited_sidecar(docs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # "Never hand-edit a sidecar" is only a rule if something enforces it — a redaction or a
    # tidy-up applied here would otherwise survive silently until the next regeneration.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt").write_text(
        "redacted\n", encoding="utf-8"
    )

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["sidecar-changed"]
    assert "data/extracted/" in findings[0].detail


def test_check_verifies_sidecars_even_on_an_lfs_less_checkout(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sidecars are never LFS-tracked, so this half of the check still works where CI runs.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / PROD / "14" / "EPA - Amort.xls").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:x\n", encoding="utf-8"
    )
    (docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt").write_text("edited\n", encoding="utf-8")

    assert [f.kind for f in check(docs, PROD)] == ["sidecar-changed"]


def test_check_tolerates_a_manifest_written_before_sidecar_hashes(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An older manifest can still assert existence; it just can't detect an edit.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    path = docs / f"{PROD}-text" / "text-sidecars.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in raw["files"]:
        entry.pop("sidecar_sha256")
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    (docs / f"{PROD}-text" / "14" / "EPA - Amort.xls.txt").write_text("edited\n", encoding="utf-8")

    assert check(docs, PROD) == []


def test_check_catches_a_sidecar_no_manifest_entry_accounts_for(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / f"{PROD}-text" / "14" / "Hand Written.doc.txt").write_text("added", encoding="utf-8")

    findings = check(docs, PROD)
    assert [f.kind for f in findings] == ["orphan"]


def test_check_ignores_hash_drift_on_an_lfs_pointer(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On a checkout without `git lfs pull` the real bytes aren't there to hash; that's a missing
    # prerequisite, not evidence the sidecar is stale.
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    (docs / PROD / "14" / "EPA - Amort.xls").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:x\n", encoding="utf-8"
    )
    assert [f.kind for f in check(docs, PROD)] == []


# --- the CLI ---------------------------------------------------------------------------------
def test_cli_generates_then_verifies_a_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from watermark.cli import app
    from watermark.config import Settings

    source = tmp_path / "documents" / PROD / "14"
    source.mkdir(parents=True)
    (source / "Letter.DOC").write_bytes(_OLE2 + b"letter")
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sidecars.get_settings", lambda: settings)
    _stub_converter(monkeypatch, {"Letter.DOC": "retainage account"})
    runner = CliRunner()

    # A `data/documents/` prefix is accepted so the argument can be pasted from a path.
    result = runner.invoke(app, ["text-sidecars", f"data/documents/{PROD}"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "documents" / f"{PROD}-text" / "14" / "Letter.DOC.txt").is_file()

    assert runner.invoke(app, ["text-sidecars", PROD, "--check"]).exit_code == 0


def test_cli_check_fails_on_a_stale_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from watermark.cli import app
    from watermark.config import Settings

    source = tmp_path / "documents" / PROD / "14"
    source.mkdir(parents=True)
    (source / "Letter.DOC").write_bytes(_OLE2 + b"letter")
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sidecars.get_settings", lambda: settings)

    result = CliRunner().invoke(app, ["text-sidecars", PROD, "--check"])
    assert result.exit_code == 1
    assert "missing-manifest" in result.output


def test_cli_reports_a_missing_converter_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from watermark.cli import app
    from watermark.config import Settings

    (tmp_path / "documents" / PROD).mkdir(parents=True)
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sidecars.get_settings", lambda: settings)
    monkeypatch.setattr(text_sidecars.shutil, "which", lambda _name: None)

    result = CliRunner().invoke(app, ["text-sidecars", PROD])
    assert result.exit_code == 1
    assert "LibreOffice" in result.output


def test_the_committed_manifest_shape_round_trips(
    docs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_converter(monkeypatch, {"Shawnee Oaks Letter.DOC": "body", "EPA - Amort.xls": "rows"})
    generate(docs, PROD)
    raw = yaml.safe_load((docs / f"{PROD}-text" / "text-sidecars.yaml").read_text(encoding="utf-8"))
    assert set(raw) == {"meta", "files"}
    assert raw["meta"]["generated_by"] == "watermark text-sidecars"
    assert "Never hand-edit" in raw["meta"]["policy"]
