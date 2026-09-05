"""Stable document handles (#1887) — and the cross-runtime parity that keeps citations alive.

The handle is minted in three runtimes: Node (the Astro build), the Workers runtime (the
legacy-path redirect and `/ask` citation rendering), and here (retrieval / MCP `search_passages`
citations). Nothing raises if they disagree — a drifted handle just 404s every document
citation, quietly. So the golden vectors committed beside the TypeScript implementation are
asserted from both sides, and this module is the Python half of that guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark.site.document_id import (
    DOCUMENT_ID_LENGTH,
    DOCUMENT_ID_PINS,
    doc_permalink,
    doc_permalink_for_rel,
    document_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "web" / "packages" / "core" / "src"
VECTORS_PATH = CORE_SRC / "__fixtures__" / "document-id-vectors.json"
LIMA_DOCUMENTS = REPO_ROOT / "web" / "sites" / "lima" / "feeds" / "documents.json"

# Crockford base32, lower-cased — deliberately without i/l/o/u.
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def _vectors() -> list[dict[str, str]]:
    data = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    vectors: list[dict[str, str]] = data["vectors"]
    return vectors


def _lima_rels() -> list[str]:
    collections = json.loads(LIMA_DOCUMENTS.read_text(encoding="utf-8"))
    return [entry["rel"] for collection in collections for entry in collection["entries"]]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda v: v["note"])
def test_matches_the_frontend_golden_vectors(vector: dict[str, str]) -> None:
    """THE parity guard: `documentId.test.ts` asserts this same file from Node.

    If this fails, fix the implementation — never the fixture. A changed vector invalidates every
    document citation already published against the old handle.
    """
    assert document_id(vector["rel"]) == vector["id"]


def test_vectors_cover_the_multibyte_cases_that_break_cross_runtime_hashes() -> None:
    """UTF-8 width is where a JS/Python hash port actually diverges — JS iterates UTF-16 units."""
    notes = " ".join(v["note"] for v in _vectors())
    assert "2-byte UTF-8" in notes
    assert "3-byte UTF-8" in notes
    assert "4-byte UTF-8" in notes


def test_handles_are_fixed_width_lowercase_crockford() -> None:
    for rel in _lima_rels():
        handle = document_id(rel)
        assert len(handle) == DOCUMENT_ID_LENGTH
        assert set(handle) <= set(ALPHABET)


def test_ambiguous_glyphs_never_appear() -> None:
    """i/l/o/u are excluded so a handle re-typed off a filing can't collide via 1/l or 0/O."""
    seen = {char for rel in _lima_rels() for char in document_id(rel)}
    assert not (seen & set("ilou"))


def test_no_collision_across_the_committed_corpus() -> None:
    rels = _lima_rels()
    # 3247 → 3250 (#1966): refreshing the lagging committed Lima bundle surfaced three `odd/`
    # documents it predated — the DeWine tax-exemption-pause release and two Ohio Tax Credit
    # Authority minutes.
    # 3250 → 3251 (#1265): the same lag, again. Re-exporting Lima for the `fmtMult` fix surfaced
    # `legal/ohio-revised-code/122.17-10-3-2023.pdf`, the job-creation-tax-credit statute, which
    # the committed bundle predated. Reviewed: all 3251 handles are distinct.
    # 3251 → 3254 (#2047): three H.B. 646 witness submissions added to
    # `legal/select-committee-2026/witnesses/` (Petty, Harper, Pokladnik). They arrived inside an
    # ADAMS COUNTY production but reach the LIMA bundle, and correctly so — `legal/` is network-
    # global, not peer-scoped, so the reference build reads it. The other 48 files of that same
    # production do NOT appear here, because `west-union/` and `usace/west-union/` are west-union's
    # eponymous prefixes and are subtracted from Lima's scope (#1505). Reviewed: all 3254 distinct.
    # 3254 → 3348 (#2072 follow-on): 93 `oepa/lima/edoc-*.pdf` — the enforcement, inspection and
    # permit-action tranche of the City of Lima WWTP's NPDES record on permit 2PE00000 — plus
    # `plans/4091285.pdf`, the Notice of Intent completing the `2GC08747` Bosc storm-outfall set.
    # They reach the LIMA bundle directly rather than by network-global scope: both `oepa/lima/`
    # and Lima's flat `plans/` are its own prefixes.
    # The portal pull resolved 261 documents and 168 are deliberately NOT committed (routine
    # reports, monitoring/sampling, plan sets, and 16 permit-application packages that were alone
    # ~712 MB) — the repository exceeded its Git-LFS budget. Their docids live in
    # `data/research/oepa-portal-2pe00000-2026-08-22/manifest.yaml` and each is re-fetchable, so a
    # later commit of any of them moves this number again and SHOULD.
    # Reviewed: 3348 rels, 3348 distinct rels, 3348 distinct handles — zero collisions. Checked as a
    # set rather than inferred from the count, because "the number moved by what I expected" is not
    # evidence of anything on a jump this size.
    # 3348 → 3350 (#2088): the two Bistrozzi eDocuments of the 2026-08-14 BOSC-1A sanitary PTI
    # Rev. 1 — `permits/bistrozzi-permits/4230060.pdf` (the issued DSWPTI-260597) and `4230068.pdf`
    # (its approved ePlan application). They reach the LIMA bundle because `permits/` is one of
    # Lima's own prefixes.
    # ⚠️ The same permit action served TWO MORE eDocuments that are deliberately NOT committed:
    # `4230061` (17 pp site plan, 23.95 MB) and `4230062` (13 pp sanitary plan & profile, 14.45 MB).
    # Both were fetched, opened and content-verified on 2026-08-23; the Git-LFS budget is exceeded,
    # so they are deferred with their sha256 recorded in
    # `data/documents/permits/bistrozzi-permits/filename-map.yaml` and each is re-fetchable by
    # docid. Committing either moves this number again and SHOULD. Publication of the drawings is a
    # separate reviewed decision (#274/#281) — they carry security-relevant site detail.
    # Reviewed: 3350 rels, 3350 distinct rels, 3350 distinct handles — zero collisions, checked as
    # a set rather than inferred from the delta.
    # 3350 → 3362 (#2089): the twelve eDocuments of the 2DP00130 / APP285104563 indirect-discharge
    # application package, shelved under `oepa/lima/` because that is where `watermark oepa fetch`
    # writes an Ohio EPA pull for this site. ⚠️ THE PORTAL SERVES 23 ROWS AND THIS NUMBER MOVES BY
    # TWELVE, WHICH IS THE POINT: the package is the same bundle filed three times and resolves to
    # 16 distinct documents, of which eleven are exact byte-duplicates (7) or text-identical
    # re-submissions whose PDF bytes differ (4). Those eleven are recorded by sha256 — and, where
    # the bytes differ, by the hash of their extracted text — in
    # `data/documents/oepa/lima/2dp00130-app285104563-manifest.yaml`, which accounts for all 23
    # docids. This is COMPLETE coverage of the package, not an LFS deferral.
    # Reviewed: 3362 rels, 3362 distinct rels, 3362 distinct handles — zero collisions, checked as
    # a set rather than inferred from the delta.
    # 3362 → 3382 (City of Lima PRR, #1536): the twenty committed files of the City of Lima's first
    # public-records production, delivered in two rolling partial responses (2026-08-22 batch 1,
    # Part A; 2026-08-24 batch 2, Parts B/C/F) and shelved under
    # `legal/prr-mandamus/prr-production-2026-08-{22,24}-lima/`. They reach the LIMA bundle because
    # `legal/` is network-global, the same route the H.B. 646 witness submissions took above.
    # ⚠️ TWENTY-TWO FILES WERE DELIVERED AND THIS NUMBER MOVES BY TWENTY, WHICH IS THE POINT: the
    # City produced `2PE00000.pdf` (the issued permit) and `2026.July_Lima_NOV.pdf`, both
    # byte-identical to documents the corpus already held from Ohio EPA — the permit to BOTH
    # `oepa/2PE00000.pdf` and `oepa/lima/edoc-2363112.pdf` (a pre-existing internal duplicate this
    # checksum pass surfaced), the NOV to `oepa/lima/edoc-4192703.pdf`. Per the CLAUDE.md rule that
    # removal is permitted only for a checksum-verified byte-identical duplicate, neither was
    # re-committed; both are recorded with their verifying sha256 under `cross_corpus_duplicates`
    # in `data/extracted/legal/prr-mandamus/bosc-prr-production-2026-08-lima.custody-manifest.yaml`,
    # which accounts for all 22 delivered files. This is COMPLETE coverage of the production, not
    # an LFS deferral.
    # Reviewed: 3382 rels, 3382 distinct rels, 3382 distinct handles — zero collisions, checked as
    # a set rather than inferred from the delta.
    # 3382 → 3394 (the §401 backfill): the Project BOSC water-quality certifications
    # `DSW401251760W` and `DSW401252260W`, shelved on the existing `permits/bistrozzi-permits/`
    # shelf under its established bare-`<docid>.pdf` naming. ⚠️ THE SWEEP LISTED 18 ROWS AND THIS
    # NUMBER MOVES BY TWELVE, WHICH IS THE POINT: the portal serves several exhibits at more than
    # one docid — and one exhibit under BOTH certifications — so the 18 rows are 12 distinct
    # byte-streams. The six duplicate docids are recorded in `also_served_as` in that shelf's
    # `filename-map.yaml`, which accounts for all 18. Complete coverage, not a deferral.
    # Reviewed: 3394 rels, 3394 distinct rels, 3394 distinct handles — zero collisions, checked as
    # a set rather than inferred from the delta.
    assert len(rels) == 3394, "a corpus change belongs in review, not a silent collision"
    assert len({document_id(rel) for rel in rels}) == len(rels)
    # The count alone is a weak proxy: a delete-one-add-one leaves it at 3362. Name the two
    # committed BOSC-1A eDocs, and assert the two DEFERRED plan sets are absent — the deferral
    # is a deliberate, recorded decision (filename-map.yaml), not an accident of the fetch.
    # Committing either plan set SHOULD fail here: fix it by updating the manifest's `deferred:`
    # block in the same change, never by deleting the assertion.
    shelf = "permits/bistrozzi-permits/"
    assert {f"{shelf}4230060.pdf", f"{shelf}4230068.pdf"} <= set(rels)
    assert not {f"{shelf}4230061.pdf", f"{shelf}4230062.pdf"} & set(rels)
    # The §401 backfill, held to the same discipline, and here the ABSENT set carries the weight:
    # the six duplicate docids must never be committed, because the shelf already holds those exact
    # bytes under the docid the portal served them at first. Committing one would inflate the
    # corpus with bytes its own filename-map says it already has. Fix a failure by updating
    # `also_served_as` in that map, never by editing this.
    committed_401 = {
        f"{shelf}{d}.pdf"
        for d in (
            "3702677",
            "3702678",
            "3702679",
            "3702680",
            "3702681",
            "3702682",
            "3702684",
            "3727949",
            "3728018",
            "3933660",
            "3933661",
            "4011312",
        )
    }
    duplicates_401 = {
        f"{shelf}{d}.pdf"
        for d in ("3727545", "3727546", "3727547", "3727548", "3974497", "3974498")
    }
    assert committed_401 <= set(rels)
    assert not duplicates_401 & set(rels)
    # Same discipline for the 2DP00130 package, and here the absent set is the load-bearing half:
    # committing a duplicate would inflate the corpus with bytes the manifest says it already
    # holds. Fix a failure by updating that manifest in the same change, never by editing this.
    oepa_lima = "oepa/lima/edoc-{}.pdf"
    committed_2dp = {
        oepa_lima.format(d)
        for d in (
            "4116201",
            "4116202",
            "4116203",
            "4116204",
            "4116205",
            "4116206",
            "4116207",
            "4116225",
            "4116226",
            "4116227",
            "4116228",
            "4116229",
        )
    }
    duplicates_2dp = {
        oepa_lima.format(d)
        for d in (
            "4116218",
            "4116219",
            "4116220",
            "4116221",
            "4116222",
            "4116223",
            "4116224",
            "4116232",
            "4116233",
            "4116234",
            "4116235",
        )
    }
    assert committed_2dp <= set(rels)
    assert not duplicates_2dp & set(rels)
    assert len(committed_2dp) + len(duplicates_2dp) == 23, "the portal serves 23 rows on 2DP00130"
    # Same discipline for the City of Lima production. The absent set is again load-bearing: the
    # City handed back two records the corpus already holds byte-for-byte, and committing either
    # would inflate the corpus with bytes the custody manifest says it already has. Fix a failure
    # by updating that manifest in the same change, never by editing this.
    lima_prr_batch1 = {
        "legal/prr-mandamus/prr-production-2026-08-22-lima/"
        "City_of_Lima_NPDES_Permit_Renewal_Application_03012022.pdf"
    }
    shelf2 = "legal/prr-mandamus/prr-production-2026-08-24-lima/"
    lima_prr_batch2 = (
        {
            f"{shelf2}Acceptance_Letter_{d}.pdf"
            for d in (
                "8-31-23",
                "1-24-24",
                "4-2-24",
                "5-29-24",
                "6-4-24",
                "7-15-24",
                "8-5-24",
                "9-18-24",
                "1-31-25",
                "6-4-26",
            )
        }
        | {
            f"{shelf2}Ammonium_Results_Week_of_{w}_26.xlsx"
            for w in ("01_18", "01_25", "02_01", "02_08", "02_15", "02_22")
        }
        | {
            f"{shelf2}Allen_County_Biosolids_Contract_6_3_24.pdf",
            f"{shelf2}January_2026_Noncompliance_Report_Ammonia.pdf",
            f"{shelf2}February_2026_Noncompliance_Report_Ammonia.pdf",
        }
    )
    lima_prr_duplicates = {
        f"{shelf2}2026.July_Lima_NOV.pdf",
        "legal/prr-mandamus/prr-production-2026-08-22-lima/2PE00000.pdf",
    }
    assert lima_prr_batch1 | lima_prr_batch2 <= set(rels)
    assert not lima_prr_duplicates & set(rels)
    assert len(lima_prr_batch1) + len(lima_prr_batch2) + len(lima_prr_duplicates) == 22, (
        "the City delivered 22 files across the two batches"
    )
    # The bytes the two duplicates carry ARE in the corpus, at their Ohio EPA shelf — assert that,
    # so "not committed here" can never quietly become "not held at all".
    assert {
        "oepa/2PE00000.pdf",
        "oepa/lima/edoc-2363112.pdf",
        "oepa/lima/edoc-4192703.pdf",
    } <= set(rels)


def test_rel_is_taken_verbatim() -> None:
    """The rel is the as-received custody path; normalizing here would fork its definition."""
    assert document_id("A/B.pdf") != document_id("a/b.pdf")
    distinct = {document_id(r) for r in ("a/b c.pdf", "a/b%20c.pdf", "a/b&c.pdf", "a/b#c.pdf")}
    assert len(distinct) == 4


def test_pins_are_empty_and_match_the_frontend() -> None:
    """Both sides ship no pins, so every handle is reproducible from the corpus alone.

    Reads the pin literal out of the TypeScript source rather than re-declaring the expectation:
    an entry added on one side only would silently break the other runtime's resolution.
    """
    assert DOCUMENT_ID_PINS == {}
    ts_source = (CORE_SRC / "documentId.ts").read_text(encoding="utf-8")
    body = ts_source.split("DOCUMENT_ID_PINS: Readonly<Record<string, string>> = {", 1)[1]
    body = body.split("};", 1)[0]
    declared = [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    assert declared == [], f"frontend declares pins Python does not carry: {declared}"


def test_pin_wins_over_the_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    rel = "oepa/van-wert/moved.pdf"
    derived = document_id(rel)
    monkeypatch.setitem(DOCUMENT_ID_PINS, rel, "zzzzzzzz")
    assert document_id(rel) == "zzzzzzzz" != derived
    assert document_id("oepa/van-wert/other.pdf") != "zzzzzzzz"


def test_permalink_is_flat_regardless_of_corpus_depth() -> None:
    deepest = max(_lima_rels(), key=lambda rel: rel.count("/"))
    assert deepest.count("/") == 11  # 12 segments — the route it replaces rendered at 16
    assert doc_permalink_for_rel(deepest).strip("/").count("/") == 1
    assert doc_permalink("7k3m9qpb") == "/doc/7k3m9qpb/"
