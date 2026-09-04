"""The committed `vault.yaml` record of the corpus' vaulted bytes (#2143, epic #2141).

Hermetic by construction, and that is the module's central claim rather than a testing convenience:
a Git-LFS oid *is* the SHA-256 of the file's content, so the record is derivable from pointers alone
and every unit test here builds manifests over synthetic trees with no LFS, no git and no network.

One test at the bottom does read the real repository, because the invariant that matters most —
every tracked path recorded exactly once, at the oid git reports — cannot be asserted over a
fixture. It skips where `git lfs` is unavailable rather than failing.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from watermark.documents.vault import (
    MANIFEST_NAME,
    UnaddressableError,
    VaultArtifact,
    build,
    check,
    collection_of,
    content_address,
    load_manifest,
    manifest_path,
    parse_pointer,
    tracked_rels,
    write,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_CONTENT = b"%PDF-1.4\nthe bytes a council minute is made of\n"
_SHA = hashlib.sha256(_CONTENT).hexdigest()


def _pointer(oid: str, size: int) -> bytes:
    return (
        b"version https://git-lfs.github.com/spec/v1\n"
        + f"oid sha256:{oid}\nsize {size}\n".encode()
    )


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    (d / "documents" / "aedg").mkdir(parents=True)
    (d / "reference" / "usgs").mkdir(parents=True)
    return d


# --- the pointer parser -------------------------------------------------------


def test_a_well_formed_pointer_yields_its_oid_and_the_content_size() -> None:
    parsed = parse_pointer(_pointer(_SHA, 4242))
    assert parsed is not None
    assert parsed.oid == _SHA
    # The size line carries the CONTENT's length, not the stub's — that distinction is the whole
    # reason a manifest can record true sizes without materializing anything.
    assert parsed.size == 4242


def test_real_bytes_are_not_mistaken_for_a_pointer() -> None:
    assert parse_pointer(_CONTENT) is None
    assert parse_pointer(b"") is None


@pytest.mark.parametrize(
    "head",
    [
        b"version https://git-lfs.github.com/spec/v1\nsize 10\n",  # no oid
        b"version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 10\n",  # short oid
        b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"z" * 64 + b"\nsize 1\n",
        b"version https://git-lfs.github.com/spec/v1\noid sha256:" + _SHA.encode() + b"\nsize x\n",
    ],
)
def test_a_mangled_pointer_is_refused_rather_than_partially_believed(head: bytes) -> None:
    """A truncated or hand-edited stub is not something to take a content address from.

    Returning a half-parsed pointer would put a wrong digest in a committed record, which is
    strictly worse than reporting that the file cannot be addressed.
    """
    assert parse_pointer(head) is None


# --- the invariant the whole design rests on ----------------------------------


def test_the_pointer_and_the_real_bytes_give_the_same_content_address(tmp_path: Path) -> None:
    """The load-bearing equivalence: an oid is the sha256 of the content.

    If this ever stopped holding, a manifest written on a `git lfs pull`ed machine would disagree
    with one written in CI, and `--check` would fail on the difference between two correct runs.
    """
    materialized = tmp_path / "real.pdf"
    materialized.write_bytes(_CONTENT)
    unresolved = tmp_path / "pointer.pdf"
    unresolved.write_bytes(_pointer(_SHA, len(_CONTENT)))

    assert content_address(materialized) == (_SHA, len(_CONTENT))
    assert content_address(unresolved) == content_address(materialized)


def test_an_absent_or_unreadable_file_has_no_address_rather_than_a_guessed_one(
    tmp_path: Path,
) -> None:
    assert content_address(tmp_path / "nope.pdf") is None


def test_a_file_larger_than_one_read_buffer_hashes_whole(tmp_path: Path) -> None:
    """The head is read first to test for a pointer, so it must still reach the digest."""
    blob = b"\x00\xff" * (1 << 20)  # 2 MiB, spanning the 256-byte head and several 1 MiB chunks
    path = tmp_path / "scan.tif"
    path.write_bytes(blob)
    assert content_address(path) == (hashlib.sha256(blob).hexdigest(), len(blob))


# --- grouping -----------------------------------------------------------------


def test_a_rel_is_grouped_by_its_first_level_collection() -> None:
    assert collection_of("documents/aedg/PRR-01-bundle.ocr.pdf") == "documents/aedg"
    assert collection_of("documents/american-township/meetings/1-12-26 minutes.docx") == (
        "documents/american-township"
    )
    assert collection_of("reference/usgs/low-flow/sir20245075.pdf") == "reference/usgs"


def test_a_root_level_file_raises_rather_than_inventing_a_manifest_for_it() -> None:
    """Every vaulted file lives in a collection; a root-level one is an anomaly to surface."""
    with pytest.raises(ValueError, match="no collection"):
        collection_of("documents/stray.pdf")


# --- build / write / check ----------------------------------------------------


def _seed(data_dir: Path, rels: dict[str, bytes]) -> None:
    for rel, payload in rels.items():
        path = data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def test_build_writes_one_manifest_per_collection_spanning_both_roots(data_dir: Path) -> None:
    rels = {
        "documents/aedg/a.pdf": _CONTENT,
        "documents/aedg/nested/b.pdf": b"%PDF-b",
        "reference/usgs/c.pdf": b"%PDF-c",
    }
    _seed(data_dir, rels)

    manifests = build(data_dir, data_dir.parent, rels=list(rels))
    assert [m.meta.collection for m in manifests] == ["documents/aedg", "reference/usgs"]

    write(data_dir, manifests)
    aedg = load_manifest(data_dir, "documents/aedg")
    assert aedg is not None
    assert [a.rel for a in aedg.artifacts] == [
        "documents/aedg/a.pdf",
        "documents/aedg/nested/b.pdf",
    ]
    assert aedg.meta.counts == {"artifacts": 2, "bytes": len(_CONTENT) + 6, "distinct_addresses": 2}
    assert manifest_path(data_dir, "reference/usgs").name == MANIFEST_NAME


def test_the_as_received_name_survives_verbatim(data_dir: Path) -> None:
    """Spaces, upper-case extensions and a missing extension are all recorded as they are.

    The corpus carries all three deliberately — a source filename is never "fixed" — so a record
    that normalized them would not describe the tree it claims to.
    """
    rels = {
        "documents/aedg/1-12-26 minutes.docx": b"PK\x03\x04",
        "documents/aedg/SHOUTING.PDF": b"%PDF-x",
        "documents/aedg/3-3-16 Natale Revised Change Order": b"%PDF-y",
    }
    _seed(data_dir, rels)
    write(data_dir, build(data_dir, data_dir.parent, rels=list(rels)))

    manifest = load_manifest(data_dir, "documents/aedg")
    assert manifest is not None
    assert [a.rel for a in manifest.artifacts] == sorted(rels)


def test_media_type_comes_from_the_extension_not_a_content_sniff(data_dir: Path) -> None:
    """A pointer has no sniffable bytes, so a sniff would make the record checkout-dependent.

    The extensionless file falls back rather than being sniffed as the PDF its pointer describes,
    and a `.docx` pointer still types as a `.docx` — which is what the deployed feed reports too,
    since the production build never pulls LFS either.
    """
    rels = {
        "documents/aedg/deck.pdf": _pointer(_SHA, 9),
        "documents/aedg/minutes.docx": _pointer("b" * 64, 9),
        "documents/aedg/3-3-16 Natale Revised Change Order": _pointer("c" * 64, 9),
    }
    _seed(data_dir, rels)
    write(data_dir, build(data_dir, data_dir.parent, rels=list(rels)))

    manifest = load_manifest(data_dir, "documents/aedg")
    assert manifest is not None
    by_rel = {a.rel: a.media_type for a in manifest.artifacts}
    assert by_rel["documents/aedg/deck.pdf"] == "application/pdf"
    assert by_rel["documents/aedg/minutes.docx"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert by_rel["documents/aedg/3-3-16 Natale Revised Change Order"] == (
        "application/octet-stream"
    )


def test_two_custody_paths_to_one_blob_keep_both_entries(data_dir: Path) -> None:
    """476 files in the real corpus are byte-duplicates of another. Both rels are facts.

    Deduplication is the store's business — content addressing gives it for free — and collapsing
    them in the record would lose a custody path.
    """
    rels = {"documents/aedg/original.pdf": _CONTENT, "documents/aedg/refiled.pdf": _CONTENT}
    _seed(data_dir, rels)
    manifest = build(data_dir, data_dir.parent, rels=list(rels))[0]

    assert len(manifest.artifacts) == 2
    assert {a.sha256 for a in manifest.artifacts} == {_SHA}
    assert manifest.meta.counts == {
        "artifacts": 2,
        "bytes": 2 * len(_CONTENT),
        "distinct_addresses": 1,
    }


def test_redistributable_is_written_on_every_artifact(data_dir: Path) -> None:
    """Public records throughout, and stated rather than defaulted.

    yidam refuses a push per-artifact, and that refusal only means something if the assertion was
    made. Serialization must therefore carry the key even though its value is the permissive one.
    """
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))

    raw = yaml.safe_load(manifest_path(data_dir, "documents/aedg").read_text())
    assert raw["artifacts"][0]["redistributable"] is True
    assert "redistributable" in raw["artifacts"][0]


def test_build_refuses_when_a_tracked_file_cannot_be_addressed(data_dir: Path) -> None:
    """A manifest missing entries is worse than none: it reads as complete."""
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    with pytest.raises(UnaddressableError, match="refusing to write"):
        build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf", "documents/aedg/gone.pdf"])


def test_rewriting_an_unchanged_collection_is_a_no_op(data_dir: Path) -> None:
    """A no-op regeneration must not dirty the record, or the diff stops carrying information.

    The record is reviewed by reading what changed, like an extraction — so a fresh `generated_at`
    on 35 untouched files is noise that hides the one collection that actually moved.
    """
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    first = write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))
    assert len(first) == 1
    stamped = load_manifest(data_dir, "documents/aedg")
    assert stamped is not None

    again = write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))
    assert again == []
    after = load_manifest(data_dir, "documents/aedg")
    assert after is not None
    assert after.meta.generated_at == stamped.meta.generated_at


def test_a_changed_collection_is_rewritten(data_dir: Path) -> None:
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))
    _seed(data_dir, {"documents/aedg/b.pdf": b"%PDF-b"})

    rels = ["documents/aedg/a.pdf", "documents/aedg/b.pdf"]
    assert len(write(data_dir, build(data_dir, data_dir.parent, rels=rels))) == 1
    manifest = load_manifest(data_dir, "documents/aedg")
    assert manifest is not None
    assert [a.rel for a in manifest.artifacts] == rels


# --- drift --------------------------------------------------------------------


def test_check_is_clean_over_a_freshly_written_manifest(data_dir: Path) -> None:
    rels = {"documents/aedg/a.pdf": _CONTENT, "reference/usgs/c.pdf": b"%PDF-c"}
    _seed(data_dir, rels)
    write(data_dir, build(data_dir, data_dir.parent, rels=list(rels)))
    assert check(data_dir, data_dir.parent, rels=list(rels)) == []


def test_a_tracked_file_in_no_manifest_is_reported_unrecorded(data_dir: Path) -> None:
    """The finding that matters most: after the untrack, this is a source byte with no record."""
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT, "documents/aedg/new.pdf": b"%PDF-n"})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))

    findings = check(
        data_dir, data_dir.parent, rels=["documents/aedg/a.pdf", "documents/aedg/new.pdf"]
    )
    assert [(f.kind, f.rel) for f in findings] == [("unrecorded", "documents/aedg/new.pdf")]


def test_replaced_bytes_are_reported_as_a_changed_address(data_dir: Path) -> None:
    """Chain of custody forbids this outright, so the check names it rather than re-recording it."""
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))
    (data_dir / "documents/aedg/a.pdf").write_bytes(b"%PDF-different-and-longer")

    kinds = {f.kind for f in check(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])}
    assert kinds == {"address-changed", "size-changed"}


def test_a_recorded_file_no_longer_tracked_is_reported_orphaned(data_dir: Path) -> None:
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))

    findings = check(data_dir, data_dir.parent, rels=[])
    assert [(f.kind, f.rel) for f in findings] == [("orphaned", "documents/aedg/a.pdf")]


def test_a_recorded_file_absent_here_is_missing_not_drift(data_dir: Path) -> None:
    """An unreadable file on a partial checkout is not evidence the record is wrong."""
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    write(data_dir, build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"]))
    (data_dir / "documents/aedg/a.pdf").unlink()

    findings = check(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])
    assert [(f.kind, f.rel) for f in findings] == [("missing", "documents/aedg/a.pdf")]


def test_a_hand_edited_media_type_is_reported(data_dir: Path) -> None:
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    manifest = build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])[0]
    manifest.artifacts[0] = manifest.artifacts[0].model_copy(update={"media_type": "text/plain"})
    write(data_dir, [manifest])

    findings = check(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])
    assert [f.kind for f in findings] == ["media-changed"]


def test_the_same_rel_recorded_in_two_manifests_is_reported(data_dir: Path) -> None:
    """`exactly once` is the invariant, so a second occurrence has to surface somewhere."""
    _seed(data_dir, {"documents/aedg/a.pdf": _CONTENT})
    written = build(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])[0]
    write(data_dir, [written])
    duplicate = written.model_copy(
        update={"meta": written.meta.model_copy(update={"collection": "reference/usgs"})}
    )
    write(data_dir, [duplicate])

    findings = check(data_dir, data_dir.parent, rels=["documents/aedg/a.pdf"])
    assert [(f.kind, f.rel) for f in findings] == [("duplicated", "documents/aedg/a.pdf")]


# --- hydration ----------------------------------------------------------------


@pytest.fixture
def vaulted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A `data/` tree holding only manifests, plus a cache holding the bytes they name."""
    from watermark.documents import vault as vault_mod

    data_dir = tmp_path / "data"
    cache = tmp_path / "cache"
    files = {"documents/aedg/a b.pdf": _CONTENT, "documents/aedg/NO-EXTENSION": b"%PDF-x"}
    for rel, payload in files.items():
        path = data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    write(data_dir, build(data_dir, tmp_path, rels=list(files)))
    for rel, payload in files.items():
        sha = hashlib.sha256(payload).hexdigest()
        blob = vault_mod.cache_path(cache, sha)
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(payload)
        (data_dir / rel).unlink()  # the working tree is now empty of sources
    monkeypatch.setattr(vault_mod, "cache_dir", lambda _s=None: cache)
    return data_dir, cache


def test_hydration_restores_an_empty_tree_under_the_as_received_names(
    vaulted: tuple[Path, Path],
) -> None:
    """The acceptance criterion — and the reason this exists instead of `vault materialize`.

    Upstream would have written `<slug>-<hash8>.<ext>`, turning `NO-EXTENSION` into `.bin` and
    losing the space in `a b.pdf`. Both names survive here because the name is evidence.
    """
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    outcomes = hydrate(data_dir)

    assert {o.action for o in outcomes} == {"linked"}
    assert (data_dir / "documents/aedg/a b.pdf").read_bytes() == _CONTENT
    assert (data_dir / "documents/aedg/NO-EXTENSION").read_bytes() == b"%PDF-x"


def test_hydration_hardlinks_rather_than_copying(vaulted: tuple[Path, Path]) -> None:
    """3.6 GB does not need a second copy on disk to be readable."""
    from watermark.documents.vault import cache_path, hydrate

    data_dir, cache = vaulted
    hydrate(data_dir)
    target = data_dir / "documents/aedg/a b.pdf"
    assert target.stat().st_ino == cache_path(cache, _SHA).stat().st_ino


def test_hydration_is_idempotent(vaulted: tuple[Path, Path]) -> None:
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    hydrate(data_dir)
    assert {o.action for o in hydrate(data_dir)} == {"present"}


def test_hydration_refuses_to_overwrite_bytes_that_disagree_with_the_record(
    vaulted: tuple[Path, Path],
) -> None:
    """The custody guarantee: hydration must never be the thing that altered a source byte.

    A tool that resolved a divergence by overwriting it would destroy the evidence that there was
    one — so a conflict is reported and the file is left exactly as found.
    """
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    target = data_dir / "documents/aedg/a b.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"tampered, and not what the manifest records")

    outcomes = {o.rel: o for o in hydrate(data_dir)}
    conflict = outcomes["documents/aedg/a b.pdf"]
    assert conflict.action == "conflict"
    assert "left untouched" in conflict.detail
    assert target.read_bytes() == b"tampered, and not what the manifest records"


def test_check_mode_writes_nothing(vaulted: tuple[Path, Path]) -> None:
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    assert {o.action for o in hydrate(data_dir, check=True)} == {"linked"}
    assert not (data_dir / "documents/aedg/a b.pdf").exists()


def test_an_artifact_absent_from_the_cache_is_reported_not_invented(
    vaulted: tuple[Path, Path],
) -> None:
    from watermark.documents.vault import cache_path, hydrate

    data_dir, cache = vaulted
    cache_path(cache, _SHA).unlink()
    outcomes = {o.rel: o for o in hydrate(data_dir)}
    assert outcomes["documents/aedg/a b.pdf"].action == "absent-from-cache"
    assert "vault pull" in outcomes["documents/aedg/a b.pdf"].detail


def test_an_unresolved_pointer_is_named_rather_than_read_as_satisfied(
    vaulted: tuple[Path, Path],
) -> None:
    """⚠️ The trap this check exists for: a pointer HASH-MATCHES the record.

    An oid is the sha256 of the content, which is what makes the manifest derivable without the
    bytes — and would make a naive "does it match?" check read an unmaterialized stub as fine. It
    is not fine: nothing can read it, and `bundle-freshness.yml` guards this today precisely
    because a pointer parsed as data yields zero rows rather than an error.
    """
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    target = data_dir / "documents/aedg/a b.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_pointer(_SHA, len(_CONTENT)))

    checked = {o.rel: o for o in hydrate(data_dir, check=True)}
    assert checked["documents/aedg/a b.pdf"].action == "pointer"
    assert target.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1")


def test_hydration_replaces_a_pointer_with_the_bytes_it_names(
    vaulted: tuple[Path, Path],
) -> None:
    """Replacing a stub is not altering a source byte — the oid says which bytes belong there."""
    from watermark.documents.vault import hydrate

    data_dir, _ = vaulted
    target = data_dir / "documents/aedg/a b.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_pointer(_SHA, len(_CONTENT)))

    outcomes = {o.rel: o for o in hydrate(data_dir)}
    assert outcomes["documents/aedg/a b.pdf"].action == "linked"
    assert target.read_bytes() == _CONTENT


def test_recorded_rels_answers_after_git_lfs_stops_answering(vaulted: tuple[Path, Path]) -> None:
    """`tracked_rels` asks Git-LFS, which returns nothing after #2147. This is what remains.

    That the committed record still answers is the whole reason it is committed.
    """
    from watermark.documents.vault import recorded_rels

    data_dir, _ = vaulted
    assert recorded_rels(data_dir) == [
        "documents/aedg/NO-EXTENSION",
        "documents/aedg/a b.pdf",
    ]


# --- the real corpus ----------------------------------------------------------

_HAS_GIT_LFS = shutil.which("git") is not None and (
    subprocess.run(
        ["git", "lfs", "version"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).returncode
    == 0
)


@pytest.mark.skipif(not _HAS_GIT_LFS, reason="git-lfs unavailable; cannot enumerate tracked paths")
def test_every_tracked_path_is_recorded_exactly_once_at_the_oid_git_reports() -> None:
    """The #2143 acceptance invariant, asserted against the real repository.

    Deliberately compares against `git lfs ls-files -l` rather than against `content_address`: the
    latter is what wrote the manifests, so checking it against itself would prove only that the code
    is consistent with itself. git is the independent witness.
    """
    data_dir = REPO_ROOT / "data"
    tracked = tracked_rels(REPO_ROOT)
    if not tracked:  # after #2147 nothing is LFS-tracked and this invariant retires
        pytest.skip("no Git-LFS-tracked paths at HEAD")

    oids: dict[str, str] = {}
    out = subprocess.run(
        ["git", "lfs", "ls-files", "--long"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for line in out.splitlines():
        oid, _, path = line.partition(" ")
        rel = path[2:].removeprefix("data/")  # strip the "* " / "- " status flag
        oids[rel] = oid

    recorded: dict[str, VaultArtifact] = {}
    for path in sorted(data_dir.glob("*/*/" + MANIFEST_NAME)):
        collection = f"{path.parent.parent.name}/{path.parent.name}"
        manifest = load_manifest(data_dir, collection)
        assert manifest is not None
        assert manifest.meta.collection == collection, f"{path} names a different collection"
        for artifact in manifest.artifacts:
            assert artifact.rel not in recorded, f"{artifact.rel} recorded twice"
            assert collection_of(artifact.rel) == collection, (
                f"{artifact.rel} filed under {collection}"
            )
            recorded[artifact.rel] = artifact

    assert set(tracked) == set(recorded), "tracked paths and recorded artifacts disagree"
    mismatched = {
        rel: (artifact.sha256, oids[rel])
        for rel, artifact in recorded.items()
        if artifact.sha256 != oids.get(rel)
    }
    assert not mismatched, f"manifest sha256 != git-lfs oid for {len(mismatched)} path(s)"
