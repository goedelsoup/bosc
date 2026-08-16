"""Whole-tree guards on the record classifier's reach (#1993).

:mod:`watermark.site.records` decides what a committed extraction *is*, and it is the only thing
standing between the corpus and the `records` feed, the per-site record pages, the citation layer,
the entity graph, search and `/ask`. #1993 widened it from 137 recognized files to 169. These
assertions are the ones that would have caught every fatal defect that widening produced in
design: a rule that steals a record it was never meant to claim, a generic key that sweeps in the
next extraction to use the word, a payload that publishes this repo's own working notes as if they
were fields read off an instrument.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import pytest
import yaml

from watermark.site.documents import build_doc_index, export_documents
from watermark.site.feeds import RecordGroup
from watermark.site.records import (
    _BLOCK_TO_GROUP,
    _META_KIND_TO_GROUP,
    _WHOLE_DOC_BLOCK_TO_GROUP,
    _WORKING_NOTES,
    _classify,
    export_records,
    load_records,
)

from .conftest import EXTRACTED, REPO_ROOT

BASELINE = Path(__file__).parent / "fixtures" / "site" / "records-baseline.json"
DOCUMENTS = REPO_ROOT / "data" / "documents"


def _committed() -> dict[str, dict[str, Any]]:
    """Every committed extraction, by rel-path, parsed once."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(EXTRACTED.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            out[str(path.relative_to(EXTRACTED))] = data
    return out


def test_no_committed_extraction_changes_group() -> None:
    """A classifier addition may only ADD records — never move one that already publishes.

    See ``tests/fixtures/site/README.md``: regenerating the baseline to make this pass is how a
    silent reclassification ships.
    """
    baseline: dict[str, str] = json.loads(BASELINE.read_text(encoding="utf-8"))
    now = {rec.rel: rec.group for rec in load_records(EXTRACTED)}
    moved = {rel: (was, now.get(rel)) for rel, was in baseline.items() if now.get(rel) != was}
    assert not moved, f"records changed group or stopped publishing: {moved}"


@pytest.mark.parametrize(
    ("key", "group", "expected"),
    [
        ("determination", "wetland-determinations", 2),
        ("statutory_notice", "statutory-notices", 2),
        ("zoning_amendment", "local-legislation", 1),
        ("zoning_application", "local-legislation", 1),
        ("sellers", "land-assembly", 1),
        ("zoning_code", "local-legislation", 1),
        ("bill", "state-legislation", 2),
        ("retention_policy", "agency-policy", 1),
        ("development_agreement", "incentive-package", 2),
        ("parties", "agreements", 7),
    ],
)
def test_each_new_key_claims_exactly_its_genre(key: str, group: str, expected: int) -> None:
    """Every key #1993 added, with its exact membership named as a count.

    A future extraction that reaches for one of these words is caught here at the diff, before it
    publishes as a genre it is not. ``parties`` is the one key whose census exceeds its group: two
    files carry it alongside a `case:` or an `order:` that must keep them, which is the ordering
    invariant asserted below.
    """
    hits = {rel: data for rel, data in _committed().items() if key in data}
    assert len(hits) == expected, f"`{key}:` census changed: {sorted(hits)}"
    claimed = {rel: (_classify(data) or ("<unclassified>",))[0] for rel, data in hits.items()}
    off = {rel: g for rel, g in claimed.items() if g != group}
    if key == "parties":  # the two files a higher-priority block keeps — see the test below
        assert off == {
            "findlay/governance/litigation-one-energy-v-allen-twp.yaml": "litigation",
            "regulatory/west-union/west-union-consent-order-1993.order.yaml": "enforcement",
        }
    else:
        assert not off, f"`{key}:` reached {off}, not {group}"


def test_meta_kind_allowlist_claims_exactly_its_members() -> None:
    """The `meta.kind` values, and how many committed files each claims."""
    census: dict[str, list[str]] = {}
    for rel, data in _committed().items():
        meta = data.get("meta")
        kind = meta.get("kind") if isinstance(meta, dict) else None
        if kind in _META_KIND_TO_GROUP:
            census.setdefault(str(kind), []).append(rel)
    assert {k: len(v) for k, v in sorted(census.items())} == {
        "grid-interconnection-need": 1,
        "grid-siting-project": 4,
        "opsb-siting-case": 1,
        "tariff-posture": 2,
        "transmission-project": 1,
    }
    for kind, rels in census.items():
        for rel in rels:
            assert _classify(_committed()[rel])[0] == _META_KIND_TO_GROUP[kind], rel


def test_meta_is_never_a_payload_block_key() -> None:
    """The single highest-value guard in this file.

    77 committed extractions carry a top-level ``meta:``, and the whole-document map is scanned
    BEFORE the IDEM rule and the OPC check. A ``meta`` entry in either block map would publish
    every meetings manifest, corpus index, completeness audit, standing watch and site footprint in
    the tree — and steal both Fort Wayne IDEM permits and the OPC summary out of their correct
    groups. The `meta.kind` value allowlist is the entire safety property, and it runs LAST.
    """
    assert "meta" not in _BLOCK_TO_GROUP
    assert "meta" not in _WHOLE_DOC_BLOCK_TO_GROUP
    with_meta = [rel for rel, data in _committed().items() if isinstance(data.get("meta"), dict)]
    assert len(with_meta) >= 70, "the census this guard defends against has moved — re-check it"
    assert _classify({"meta": {"kind": "idem"}}) == ("permits-idem", {"kind": "idem"})
    assert _classify({"meta": {"kind": "download-manifest"}, "documents": [1]}) is None
    assert _classify({"meta": {"kind": "water-watch"}}) is None
    # And it cannot outrank a payload block: an IDEM permit whose `meta.kind` is also allowlisted
    # would still be claimed by its block.
    assert _classify({"permit": {"permit_no": "2PD"}, "meta": {"kind": "tariff-posture"}}) == (
        "permits-npdes",
        {"permit_no": "2PD"},
    )


def test_a_higher_priority_block_keeps_the_files_that_carry_two_mapped_keys() -> None:
    """`parties` is LAST in the whole-document map, and the block map runs before it.

    A filed case that also names its parties is litigation, not an agreement; a consent order that
    names its parties is enforcement; an NPDES permit that carries its public-notice dates is a
    permit, not a notice. The last of those is why the two committed notices were re-keyed to
    `statutory_notice:` rather than the classifier claiming the bare `notice:` — dict insertion
    order is an invariant invisible in the source and destroyed by any future reordering.
    """
    assert _classify({"case": {"caption": "A v. B"}, "parties": {"plaintiff": "A"}})[0] == (
        "litigation"
    )
    assert _classify({"order": {"agency": "OEPA"}, "parties": {"a": 1}})[0] == "enforcement"
    assert _classify({"permit": {"permit_no": "2PD"}, "notice": {"published": "x"}})[0] == (
        "permits-npdes"
    )
    groups = {rec.rel: rec.group for rec in load_records(EXTRACTED)}
    assert groups["findlay/governance/litigation-one-energy-v-allen-twp.yaml"] == "litigation"
    assert groups["regulatory/west-union/west-union-consent-order-1993.order.yaml"] == "enforcement"
    assert groups["oepa/findlay/2PD00008.1abaf306.npdes.yaml"] == "permits-npdes"


@pytest.mark.parametrize(
    "pattern",
    [
        "bosc-site-footprint.yaml",
        "meetings/download-manifest.yaml",
        "meetings/meeting-index.yaml",
        "meetings/meeting-summaries.yaml",
        "meetings/completeness-audit.yaml",
        "filename-map.yaml",
        "*.candidates.yaml",
    ],
)
def test_machinery_and_derived_models_never_classify(pattern: str) -> None:
    """The named non-records, each verified against the code that consumes it, not its name.

    A profile's ``footprint_relpath`` input, the meetings pipeline's own manifests and indexes (the
    `meetings` feed already publishes `meeting-summaries.yaml`, so a record would double-count the
    same evidence), the chain-of-custody alias manifests the root CLAUDE.md names by path, and the
    facility candidate registers. Publishing any of them would float a site's record domain on its
    own scaffolding — the failure `records.py`'s module docstring names.
    """
    hits = list(EXTRACTED.rglob(pattern))
    assert hits, f"no committed file matches {pattern} — the guard is watching nothing"
    for path in hits:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert _classify(data) is None, path


def test_whole_document_payloads_carry_no_working_notes() -> None:
    """This repo's workflow and this repo's argument are never published as record fields.

    Without the strip, every whole-document record publishes `issue:`/`epic:`/`acceptance:` (an
    issue's acceptance criteria) and `thesis:`/`relevance:` (this repo's reading of the document)
    as if they were read off the instrument.
    """
    for rec in load_records(EXTRACTED):
        # Scoped to keys that were TOP-LEVEL in the document and survived into the payload — the
        # only path `_whole_doc_payload` governs. A block's own field that happens to share a name
        # is the block's (`idem/fort-wayne/47378f.idem.yaml` publishes `meta.subject`, the permit's
        # own subject line, and `meta` IS its payload).
        leaked = _WORKING_NOTES & set(rec.payload) & set(rec.data)
        assert not leaked, f"{rec.rel} publishes {sorted(leaked)}"


def test_records_are_legibly_titled_and_joined_to_their_instruments() -> None:
    """A record headed by a filename stem is unreadable; one with no join cannot be followed.

    Before #1993, 19 of the 32 records it publishes rendered as bare stems and 28 of 32 had no
    ``source_doc_rel``. Both are asserted as ceilings that can only improve, so a new extraction
    shape cannot quietly reintroduce either.
    """
    items = export_records(EXTRACTED, doc_index=build_doc_index(export_documents(DOCUMENTS)))
    stems = [i.rel for i in items if i.title == Path(i.rel).stem]
    unjoined = [i.rel for i in items if i.source_doc_rel is None]
    assert len(stems) <= 1, stems
    # The ceiling is the connector-only and DMR records that have no single source document, plus
    # `grid/van-wert/van-wert-haviland-138kv.project.yaml`, whose 612-page OPSB Letter of
    # Notification is deliberately uncommitted — a page cite is never invented.
    assert len(unjoined) <= 13, unjoined
    assert "grid/van-wert/van-wert-haviland-138kv.project.yaml" in unjoined


def test_every_record_group_is_reachable_and_labelled() -> None:
    """Enum ⇄ frontend labels ⇄ the study's group gates, in both directions.

    `groupLabel` falls back to the raw slug and the per-group routes are generated from `groupsOf`,
    so an unlabeled group renders a live page headed by its slug.
    """
    labels_ts = (REPO_ROOT / "web/packages/core/src/records.ts").read_text(encoding="utf-8")
    block = labels_ts.split("RECORD_GROUP_LABELS: Record<string, string> = {", 1)[1].split("};", 1)
    labelled = {
        line.split(":", 1)[0].strip().strip('"')
        for line in block[0].splitlines()
        if ":" in line and not line.strip().startswith("//")
    }
    assert set(get_args(RecordGroup)) == labelled

    from watermark.site.impact_study import (
        _ASSEMBLY_GROUPS,
        _FISCAL_GROUPS,
        _GOVERNANCE_GROUPS,
    )

    gated = set(_ASSEMBLY_GROUPS) | set(_GOVERNANCE_GROUPS) | set(_FISCAL_GROUPS)
    assert gated <= set(get_args(RecordGroup))

    # Every value the classifier can emit is a legal enum member — `RecordItem.group` is enforced,
    # so a slug that is not here makes `watermark export` raise for whichever site carries it.
    emitted = (
        set(_BLOCK_TO_GROUP.values())
        | set(_WHOLE_DOC_BLOCK_TO_GROUP.values())
        | set(_META_KIND_TO_GROUP.values())
        | {"opc", "permits-idem"}
    )
    assert emitted <= set(get_args(RecordGroup))


def test_van_wert_governance_reads_from_its_own_ordinances(
    site_bundle: Callable[[str], Path],
) -> None:
    """The ONE impact-study verdict #1993 changes at a peer: `governance` `partial` -> `data`.

    Van Wert's decision path was carried entirely inside `van-wert/mega-site-instruments.yaml` —
    a compiled instrument SET covering three ordinances, a public hearing, two council meetings,
    the land geometry, a chronology and the public comment. `load_records` yields one record per
    file, so that set can only ever publish as one thing, and a compilation is honestly neither a
    legislative act nor a conveyance. #1993 splits the three ACTS out as `resolution:` siblings.

    `assembly` does NOT move, and the split is deliberately not allowed to move it: Ordinance
    26-05-028 accepts a 901.698-acre annexation, but an annexation shifts a jurisdictional
    boundary and conveys no title. Van Wert's record still carries no conveyance instrument.
    """
    out = site_bundle("van-wert")
    study = json.loads((out / "feeds" / "impact-study.json").read_text(encoding="utf-8"))
    status = {c["chapter"]: c["model"]["status"] for c in study}
    assert status["governance"] == "data"
    assert status["assembly"] == "partial"

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    feed = next(f for f in manifest["feeds"] if f["name"] == "records")
    raw = (out / feed["path"]).read_text(encoding="utf-8")
    records = (
        [json.loads(line) for line in raw.splitlines() if line.strip()]
        if feed["path"].endswith(".ndjson")
        else json.loads(raw)
    )
    acts = {r["rel"]: r for r in records if r["group"] == "local-legislation"}
    assert len(acts) == 3, sorted(acts)
    for rec in acts.values():
        # Passage rests on the approved minutes, not on the unsigned pre-vote upload each record
        # is read from — the custody caveat must reach the feed, not just the YAML comment.
        assert any("UNSIGNED" in w for w in rec["warnings"]), rec["rel"]
