"""The `artifacts:` half of the projected catalog — what the vault routes on (#2144, epic #2141).

`.yidam/catalog/` is generated, so the record the binary reads is only ever as good as this
projection. These tests hold it to the two Error-severity checks adopting `artifacts:` arms
(`catalog-artifact-malformed`, `catalog-artifact-unroutable`) rather than to a snapshot, because a
snapshot would happily pin output the binary rejects.

Hermetic: manifests are written into a tmp `data/` tree, so nothing here reads the real corpus,
Git-LFS, or the yidam binary.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.documents.vault import build as build_manifests
from watermark.documents.vault import write as write_manifests
from watermark.site import corpus_catalog
from watermark.site.corpus_catalog import (
    VAULT_NAME,
    CatalogArtifact,
    CatalogSource,
    render_source,
    vault_sources,
)

_A = b"%PDF-a scanned council minute\n"
_B = b"%PDF-b a permit application\n"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """A `data/` tree with two vaulted collections, manifests written by the #2143 generator."""
    data_dir = tmp_path / "data"
    files = {
        "documents/aedg/deck.pdf": _A,
        "documents/aedg/nested/minutes.docx": _B,
        "reference/usgs/low-flow/sir20245075.pdf": _A,
    }
    for rel, payload in files.items():
        path = data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    write_manifests(data_dir, build_manifests(data_dir, tmp_path, rels=list(files)))
    return Settings(data_dir=data_dir, site="lima")


def test_one_source_per_vaulted_collection_across_both_roots(settings: Settings) -> None:
    sources = vault_sources(settings)
    assert [s.slug for s in sources] == ["corpus-documents-aedg", "corpus-reference-usgs"]
    assert [len(s.artifacts) for s in sources] == [2, 1]


def test_the_artifacts_come_from_the_manifests_not_from_hand_authored_yaml(
    settings: Settings,
) -> None:
    aedg = next(s for s in vault_sources(settings) if s.slug == "corpus-documents-aedg")
    manifest = yaml.safe_load((settings.data_dir / "documents/aedg/vault.yaml").read_text())
    assert [a.sha256 for a in aedg.artifacts] == [m["sha256"] for m in manifest["artifacts"]]
    assert [a.bytes for a in aedg.artifacts] == [m["bytes"] for m in manifest["artifacts"]]
    assert [a.media_type for a in aedg.artifacts] == [
        m["media_type"] for m in manifest["artifacts"]
    ]


def test_every_sha256_satisfies_catalog_artifact_malformed(settings: Settings) -> None:
    """64 lowercase hex, or the Error-severity check fires — and it names uppercase separately.

    Hex is case-insensitive and an object store is not, so two spellings would be two keys for one
    artifact. That is why this asserts the case, not just the length.
    """
    for source in vault_sources(settings):
        for artifact in source.artifacts:
            assert len(artifact.sha256) == 64
            assert all(c in "0123456789abcdef" for c in artifact.sha256)


def test_every_artifact_routes_to_the_declared_vault(settings: Settings) -> None:
    """`catalog-artifact-unroutable` (Error) compares this against `.yidam/config.toml`."""
    assert {a.vault for s in vault_sources(settings) for a in s.artifacts} == {VAULT_NAME}


def test_the_frontmatter_writes_five_keys_and_no_more(settings: Settings) -> None:
    """`from:` and `retrieved:` are omitted deliberately, and one of them would be an Error.

    A `from:` index into an entry with no `location` list names nothing, which
    `catalog-artifact-malformed` reports; and nothing in the manifests records when a given file was
    obtained, so a `retrieved:` would be invented rather than carried.
    """
    aedg = next(s for s in vault_sources(settings) if s.slug == "corpus-documents-aedg")
    front = yaml.safe_load(render_source(aedg).split("---\n")[1])

    assert set(front) == {"name", "description", "type", "artifacts"}
    assert "location" not in front, "these entries carry none, so `from:` could name nothing"
    for entry in front["artifacts"]:
        assert set(entry) == {"sha256", "bytes", "media_type", "vault", "redistributable"}


def test_redistributable_is_carried_from_the_manifest_rather_than_assumed(
    settings: Settings,
) -> None:
    """The value is `true` throughout this corpus, but the projection must not hardcode it.

    The first document obtained under a licence to read rather than to host is recorded in the
    manifest, and has to survive the trip into the catalog — otherwise the field the vault refuses
    on is a constant, and the refusal can never fire.
    """
    path = settings.data_dir / "documents/aedg/vault.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["artifacts"][0]["redistributable"] = False
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    aedg = next(s for s in vault_sources(settings) if s.slug == "corpus-documents-aedg")
    assert [a.redistributable for a in aedg.artifacts] == [False, True]


def test_a_vaulted_entry_registers_no_covers(settings: Settings) -> None:
    """A collection spans hundreds of files, so covering them would make a citation mean less.

    `covers` drives `entry_for_path`, and letting a node resolve one deed to "the whole aedg
    collection" is a weaker claim wearing a citation's clothes.
    """
    for source in vault_sources(settings):
        assert source.covers == ()


def test_vaulted_sources_come_after_the_dataset_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordering is load-bearing: `entry_for_path` returns the FIRST source covering a path.

    A dataset entry must keep precedence, so that adding the vault projection cannot change what an
    existing path resolves to.
    """
    dataset = CatalogSource(
        slug="already-registered", name="n", description="d", type="dataset", covers=("data/x",)
    )
    vaulted = CatalogSource(
        slug="corpus-documents-aedg",
        name="n",
        description="d",
        type="other",
        artifacts=(CatalogArtifact("a" * 64, 1, "application/pdf", VAULT_NAME, True),),
    )
    monkeypatch.setattr(corpus_catalog, "load_entries", lambda **_: [])
    monkeypatch.setattr(corpus_catalog, "project_entry", lambda e, s: dataset)
    monkeypatch.setattr(corpus_catalog, "vault_sources", lambda s: [vaulted])

    built = corpus_catalog.build_catalog(Settings(site="lima"))
    assert [s.slug for s in built] == [
        "corpus-documents-aedg"
    ]  # no entries -> only the vaulted one

    # With a dataset entry present, it precedes the vaulted ones.
    monkeypatch.setattr(corpus_catalog, "load_entries", lambda **_: ["one"])
    built = corpus_catalog.build_catalog(Settings(site="lima"))
    assert [s.slug for s in built] == ["already-registered", "corpus-documents-aedg"]


def test_a_dataset_entry_carries_no_artifacts(settings: Settings) -> None:
    """Committed files need no vault, so the dataset half of the projection stays unchanged."""
    source = CatalogSource(slug="s", name="n", description="d", type="dataset")
    assert source.artifacts == ()
    assert "artifacts" not in yaml.safe_load(render_source(source).split("---\n")[1])


def test_the_body_names_the_manifest_and_declines_to_be_evidence(settings: Settings) -> None:
    """The prose has to say what the entry does *not* answer, or it reads as a claim about content.

    These entries account for bytes. What the documents say lives in `data/extracted/**` under its
    own entries, and a claim rests on one of those.
    """
    aedg = next(s for s in vault_sources(settings) if s.slug == "corpus-documents-aedg")
    assert "data/documents/aedg/vault.yaml" in aedg.body
    assert "watermark documents manifest" in aedg.body
    assert "not for what they say" in aedg.body


def test_duplicate_content_across_collections_keeps_both_artifacts(settings: Settings) -> None:
    """`documents/aedg/deck.pdf` and the usgs PDF are byte-identical in this fixture.

    Each collection accounts for its own file; the vault stores one blob. That the two entries share
    a digest is the dedup working, not a collision to resolve.
    """
    sources = {s.slug: s for s in vault_sources(settings)}
    aedg = sources["corpus-documents-aedg"].artifacts[0].sha256
    usgs = sources["corpus-reference-usgs"].artifacts[0].sha256
    assert aedg == usgs == hashlib.sha256(_A).hexdigest()
