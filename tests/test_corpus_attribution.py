"""The corpus attribution overlay — #2085.

Ohio EPA's eDocument portal indexes by permit, and a sweep of permit 2PE00000 (City of Lima WWTP)
returned sixteen documents of which two are other facilities' records. ``data/extracted`` mirrors
an immutable ``data/documents``, so both stay shelved under ``oepa/lima/``; the correction happens
at the read layer, in a reviewed, document-cited overlay. These hold the overlay to being *data
about real artifacts* rather than a place to make things disappear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.sites import (
    SITES,
    CorpusScope,
    attribution_overrides,
    effective_corpus_scope,
    reattributed_in,
    reattributed_out,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = REPO_ROOT / "data" / "extracted"

MANSFIELD_LETTER = "oepa/lima/edoc-3063821.order.yaml"
RAILTECH_IPIR = "oepa/lima/edoc-3296496.order.yaml"


def test_every_override_names_a_committed_artifact_and_registered_sites() -> None:
    """The overlay is a claim about documents that exist, made against sites that exist.

    A row whose ``relpath`` no longer resolves is the failure mode that matters: the artifact
    would be gone and the overlay would still be quietly subtracting a path from a site's scope,
    which is how a reviewed correction turns into an unexplained absence.
    """
    for row in attribution_overrides():
        assert (EXTRACTED / row.relpath).exists(), f"{row.relpath} is not a committed extraction"
        assert row.shelved_under in SITES, f"{row.relpath}: unknown site {row.shelved_under!r}"
        assert row.attributed_to is None or row.attributed_to in SITES, (
            f"{row.relpath}: unknown site {row.attributed_to!r}"
        )
        assert row.relpath.startswith(f"{row.shelved_under}/") or f"/{row.shelved_under}/" in (
            f"/{row.relpath}"
        ), f"{row.relpath} is not shelved under {row.shelved_under}"
        # The evidentiary half. A re-attribution without its document-internal basis is an
        # assertion, and this file exists precisely so attribution is never one.
        assert row.basis.strip(), f"{row.relpath}: no basis recorded"
        assert row.subject.strip(), f"{row.relpath}: no subject recorded"


def test_the_two_ohio_epa_misfilings_are_declared() -> None:
    """The concrete decision #2085 recorded, asserted as data rather than as prose."""
    rows = {r.relpath: r for r in attribution_overrides()}

    mansfield = rows[MANSFIELD_LETTER]
    assert mansfield.shelved_under == "lima"
    assert mansfield.attributed_to == "mansfield"

    railtech = rows[RAILTECH_IPIR]
    assert railtech.shelved_under == "lima"
    # Henry County is not a registered site. `None` is the ANSWER, not a gap: routing this into a
    # site's record would be the very error the overlay corrects.
    assert railtech.attributed_to is None


def test_misfiled_artifacts_leave_lima_and_land_where_declared() -> None:
    """The read layer honours the overlay, and the reference build's whole-tree scope yields."""
    lima = effective_corpus_scope(SITES["lima"])
    mansfield = effective_corpus_scope(SITES["mansfield"])

    assert not lima.contains(MANSFIELD_LETTER)
    assert not lima.contains(RAILTECH_IPIR)
    assert mansfield.contains(MANSFIELD_LETTER)

    # A grant beats a narrow inclusion: Mansfield's prefixes are ("*/mansfield", "mansfield") and
    # reach nothing under oepa/lima/ on their own.
    assert not CorpusScope(include=mansfield.include).contains(MANSFIELD_LETTER)

    # The sweep's other fourteen documents are untouched — the overlay is exact paths, never a
    # prefix, so it cannot take a subtree with it.
    assert lima.contains("oepa/lima/edoc-4192703.order.yaml")
    assert lima.contains("oepa/lima/edoc-1840393.npdes.yaml")


def test_an_unattributed_artifact_reaches_exactly_no_site() -> None:
    """`attributed_to: null` means no site's cross-document layer, network-wide.

    Asserted across the whole registry rather than against Lima alone: the Henry County IPIR must
    not surface in some peer's record by an accident of prefix matching.
    """
    landed = [s for s in SITES if effective_corpus_scope(SITES[s]).contains(RAILTECH_IPIR)]
    assert landed == []


def test_no_site_reattributes_a_document_into_itself() -> None:
    """A row that changes nothing reads as a finding that there was something to change."""
    for slug in SITES:
        assert not set(reattributed_in(slug)) & set(reattributed_out(slug))


def test_overrides_do_not_disturb_a_site_that_declares_none() -> None:
    """The overlay is inert for every site it does not name — no scope may shift by its presence."""
    named = {r.shelved_under for r in attribution_overrides()} | {
        r.attributed_to for r in attribution_overrides() if r.attributed_to
    }
    for slug in SITES:
        if slug in named:
            continue
        scope = effective_corpus_scope(SITES[slug])
        assert scope.reattributed_in == ()
        assert scope.reattributed_out == ()


def test_a_missing_overlay_fails_rather_than_reverting_every_attribution(tmp_path: Path) -> None:
    """An absent overlay must raise, not read as "nothing is re-attributed".

    Loading `()` from a missing file would slide the Mansfield letter back onto Lima's chronology
    with no error anywhere — the silent revert this module exists to prevent. An overlay that is
    PRESENT and declares no overrides is the opposite: a deliberate statement, and still `()`.
    """
    import yaml

    from watermark.sites._attribution import _load

    with pytest.raises(FileNotFoundError, match="attribution overlay missing"):
        _load(tmp_path / "nope.yaml")

    empty = tmp_path / "corpus-attribution.yaml"
    empty.write_text(yaml.safe_dump({"overrides": []}), encoding="utf-8")
    assert _load(empty) == ()


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [
                {
                    "relpath": "oepa/lima/x.order.yaml",
                    "shelved_under": "lima",
                    "attributed_to": "lima",
                    "subject": "s",
                    "basis": "b",
                    "reviewed": "2026-08-23",
                }
            ],
            "already shelved under",
        ),
        (
            [
                {
                    "relpath": "oepa/lima/x.order.yaml",
                    "shelved_under": "lima",
                    "attributed_to": "mansfield",
                    "subject": "s",
                    "basis": "b",
                    "reviewed": "2026-08-23",
                },
                {
                    "relpath": "oepa/lima/x.order.yaml",
                    "shelved_under": "lima",
                    "attributed_to": "findlay",
                    "subject": "s",
                    "basis": "b",
                    "reviewed": "2026-08-23",
                },
            ],
            "duplicate override",
        ),
    ],
    ids=["self-attribution", "duplicate"],
)
def test_the_loader_refuses_a_contradictory_overlay(
    tmp_path: Path, rows: list[dict[str, object]], message: str
) -> None:
    """Two rows racing for one artifact, or a row that re-attributes a site to itself, are the
    ways this file could silently mean something other than it reads. Both fail loudly."""
    import yaml

    from watermark.sites._attribution import _load

    path = tmp_path / "corpus-attribution.yaml"
    path.write_text(yaml.safe_dump({"overrides": rows}), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        _load(path)
