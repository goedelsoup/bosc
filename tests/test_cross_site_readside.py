"""#618 — cross-site (non-Lima, non-Ohio) read-side round-trip.

The site axis (``SiteProfile`` / ``WATERMARK_SITE``) is honored on the **write / connector-input**
side but historically leaked Lima/Ohio defaults on the **read / derivation** side — the same
asymmetry that let Ohio-hardcoding through until a non-OH site (Fort Wayne) surfaced it. This
module drives the per-site reference readers (#606), the FERC seam (#608), and the cooling
basis (#607) under ``WATERMARK_SITE=fort-wayne`` (Indiana) and asserts the output is the active
site's, never Lima's. It reads only committed reference data — no network.

Note: Fort Wayne and Lima are *both* in an "Allen County", so the discriminator here is the
state (IN vs OH) and the serving utility (Indiana Michigan Power vs AEP Ohio), not the county.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.economics.baseline import load_baseline
from watermark.economics.energy import load_consumer_energy
from watermark.facility.power import derive_power_basis
from watermark.grid.ferc import derive_ferc_seam
from watermark.grid.utility import load_grid_profile
from watermark.hydrology.cooling import derive_cooling_basis

REPO_ROOT = Path(__file__).resolve().parents[1]


def _documents_rel(source: str) -> str | None:
    """The path a ``source_path`` names under ``data/documents/``, tolerant of how it was recorded —
    repo-relative, absolute (a pre-existing wart on one Lima extraction), or without the ``data/``
    prefix — so a differently-recorded but valid source is checked, not silently skipped (#1405
    review). ``None`` when the source is not a ``data/documents`` artifact at all."""
    norm = source.replace("\\", "/")
    marker = "data/documents/"
    if marker in norm:
        return norm.split(marker, 1)[1]
    if norm.startswith("documents/"):  # a `data/`-less relative record — still a real source
        return norm[len("documents/") :]
    return None


@pytest.fixture
def fw_settings() -> Settings:
    """Fort Wayne, IN — a non-Lima, non-Ohio registered site with committed reference data."""
    return Settings(
        site="fort-wayne", data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True
    )


@pytest.fixture
def lima_settings() -> Settings:
    """Lima, OH — the live reference build (the historical hardcoded default)."""
    return Settings(data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True)


# --- #780: an unscoped sibling site defaults to its OWN corpus, never Lima's whole tree ----


def test_effective_corpus_scope_defaults_to_own_slug_not_lima() -> None:
    """#780/#1505/#1405 — the safe default. Only the reference build (Lima) reads the whole tree;
    every other site reads its **eponymous** prefixes, so a freshly-registered site can't silently
    inherit Lima's Allen-County record. ``corpus_relpaths`` *adds* the prefixes no rule can derive.
    And Lima's whole tree *subtracts* every peer's scope (#1505), so it stops swallowing theirs.
    """
    from watermark.sites import SITES, effective_corpus_scope

    lima = effective_corpus_scope(SITES["lima"])
    assert lima.include is None  # reference build = whole-tree catch-all
    # #1505: whole tree MINUS every registered peer's own prefixes — a Piqua NPDES permit under
    # oepa/troy-piqua/ or a Fort Wayne §401 under idem/fort-wayne/ is no longer in Lima's scope.
    # Since #1405 those are subtracted by the derived `*/<slug>` term, not by an enumerated entry.
    assert {"*/fort-wayne", "*/troy-piqua", "springfield"} <= set(lima.exclude)
    assert not lima.contains("idem/fort-wayne/wqc.yaml")
    assert not lima.contains("oepa/troy-piqua/1PD00008.npdes.yaml")
    assert lima.contains("recorder/deed.yaml")  # Lima's own collections stay in scope
    assert lima.contains("oepa/2PE00000.npdes.yaml")  # its un-slugged Allen-County permit survives
    # A subtree that is NOBODY's record is subtracted on the same grounds (epic #1387): the
    # international candidates register is network-global, and no site is named for it, so
    # Lima's whole-tree catch-all would otherwise fold Johor and Dublin into an Allen County
    # record. Same bug as #1505, different shape — the catch-all swallows the unclaimed.
    assert "international" in set(lima.exclude)
    assert not lima.contains("international/data-center-candidates.seeded.yaml")

    # Unset → exactly the two eponymous prefixes, nothing inherited.
    assert effective_corpus_scope(SITES["springfield"]).include == ("*/springfield", "springfield")
    assert effective_corpus_scope(SITES["new-albany"]).include == ("*/new-albany", "new-albany")
    fort_wayne = effective_corpus_scope(SITES["fort-wayne"])
    assert fort_wayne.include == ("*/fort-wayne", "fort-wayne")
    assert fort_wayne.exclude == ()  # a peer includes its own prefixes and excludes nothing
    # The IDEM (Indiana) jurisdiction+site subtree reaches Fort Wayne by derivation — it used to
    # need an explicit `idem/fort-wayne` entry, which is the enumeration #1405 removed.
    assert fort_wayne.contains("idem/fort-wayne/wqc.yaml")
    assert not fort_wayne.contains("idem/somewhere-else/wqc.yaml")

    # `corpus_relpaths` survives for what no rule derives: a corpus filed by PROJECT or CASE name.
    # Urbana's Highland55 land-assembly corpus (#1328) plus the filed federal complaint that is its
    # dispute's legal spine (#1724) — the complaint sat under no peer prefix, so Lima's
    # whole-tree-minus-peers scope swallowed it while Urbana's own catalog lacked the instrument
    # its litigation record cites. Naming it moves it both ways at once, since Lima's exclusion set
    # IS the union of the peers' scopes.
    urbana = effective_corpus_scope(SITES["urbana"])
    assert urbana.include == (
        "*/urbana",
        "legal/thor-v-urbana",
        "permits/highland55",
        "urbana",
    )
    assert urbana.contains("legal/thor-v-urbana/1.pdf")
    assert urbana.contains("oepa/urbana/permit.npdes.yaml")  # derived, not enumerated
    assert not lima.contains("legal/thor-v-urbana/1.pdf")
    # Only the named subtree moves — Lima keeps the rest of `legal/` (its own PRR/mandamus record).
    assert lima.contains("legal/prr-mandamus/cra-agreement.cra.yaml")


def test_site_attributed_subtrees_reach_their_own_site() -> None:
    """#1405 — no ``<collection>/<slug>`` directory may fall outside its eponymous site's scope.

    The corpus files a site's artifacts under a collection named for the issuing agency —
    ``oepa/van-wert/``, ``idem/fort-wayne/``, ``grid/sidney/`` — and until #1405 each such subtree
    had to be *enumerated* on the profile to be reachable. That is exactly what got forgotten:
    Van Wert's NPDES permit (#1401) and Wilmington's eight (#884) sat outside the sites they
    document and inside Lima's whole-tree reference scope, so the record domain could not rise
    from permit ingest at all. This sweeps both committed trees and asserts the derivation holds
    for every registered site — the guard against the enumeration silently coming back.
    """
    from watermark.sites import SITES, effective_corpus_scope

    offenders: list[str] = []
    for tree in ("documents", "extracted"):
        root = REPO_ROOT / "data" / tree
        for collection in sorted(p for p in root.iterdir() if p.is_dir()):
            for sub in sorted(p for p in collection.iterdir() if p.is_dir()):
                if sub.name not in SITES:
                    continue
                rel = f"{collection.name}/{sub.name}"
                if not effective_corpus_scope(SITES[sub.name]).contains(rel):
                    offenders.append(f"data/{tree}/{rel} is outside {sub.name}'s corpus scope")
    assert not offenders, (
        "site-attributed subtrees orphaned from their site (#1405):\n" + "\n".join(offenders)
    )


def test_extraction_reaches_the_site_its_source_is_filed_under() -> None:
    """#1405 — if a source document is filed under ``<collection>/<slug>/``, its extraction must
    land in that site's corpus scope.

    Scope alone doesn't finish the job. Eleven OEPA extractions sat flat at
    ``data/extracted/oepa/`` while their own ``source_path`` pointed into ``oepa/van-wert/``,
    ``oepa/wilmington/`` and ``oepa/sidney/`` — so the source PDF reached the site while the
    extracted record reached Lima, and the site owned a document catalog with nothing extracted
    behind it. Every instance was detectable from the artifact itself, which is what makes this
    checkable rather than a matter of judgment.

    Deliberately narrow: it asserts only that the *site-attribution* segment survives extraction,
    not that the whole sub-path mirrors. Non-site nesting under a collection is a curation choice
    the corpus makes freely (``permits/bistrozzi-permits/`` → ``permits/``, ``wpafb/cercla/`` →
    ``wpafb/``) and is none of this guard's business.
    """
    import yaml

    from watermark.sites import SITES, effective_corpus_scope

    extracted = REPO_ROOT / "data" / "extracted"
    offenders: list[str] = []
    for path in sorted(extracted.rglob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue  # schema validity is test_extracted_yaml_valid.py's job, not this one's
        if not isinstance(doc, dict):
            continue
        source = doc.get("source_path")
        # The rel under data/documents, however the path was recorded — absolute, repo-relative, or
        # (a wart) without the `data/` prefix. A source that resolves to None is genuinely not a
        # documents artifact; one recorded in a tolerated shape must NOT be silently skipped (#1405 review).
        source_rel = _documents_rel(source) if isinstance(source, str) else None
        if source_rel is None:
            continue
        segments = source_rel.split("/")
        if len(segments) < 3 or segments[1] not in SITES:
            continue  # not a site-attributed source — nothing to preserve
        slug = segments[1]
        rel = str(path.relative_to(extracted))
        if not effective_corpus_scope(SITES[slug]).contains(rel):
            offenders.append(
                f"{path.relative_to(REPO_ROOT)} extracts {source_rel} — filed under "
                f"{segments[0]}/{slug}/ — but is outside {slug}'s corpus scope"
            )
    assert not offenders, (
        "extractions orphaned from the site their source is filed under (#1405):\n"
        + "\n".join(offenders)
    )


def test_star_slug_exclusions_are_real_attribution_not_name_collision() -> None:
    """#1405 review — guard the ONE broad term against a name collision. ``*/<slug>`` matches the
    SECOND path segment under ANY collection, so an extraction that merely *sits* at
    ``<collection>/<peer-slug>/`` is pulled out of Lima's reference build by it — correct only when
    the artifact genuinely belongs to that peer. The collision is not hypothetical vocabulary:
    ``ottawa`` is a registered peer AND Lima's own receiving river, and several peer slugs are
    common Ohio place-names, so a future Lima artifact parked under, say, ``hydrology/ottawa/`` would
    be silently subtracted from Lima with nothing to catch it.

    So for every extraction whose second path segment is a peer slug, require its own ``source_path``
    to corroborate that slug (the source is filed under ``<slug>/`` or ``<collection>/<slug>/`` too).
    A physical location that collides with a peer name but whose source attributes elsewhere is the
    exact failure mode. This targets only the ``*/<slug>`` mechanism — a first-segment slug
    collection (``findlay/…``) or a project/case prefix (``permits/dazzler-permits/…``) is exact,
    not broad, and is the sibling guard's concern. Narrow by design: an extraction with no
    ``data/documents`` source is skipped, since there is nothing to corroborate against.
    """
    import yaml

    from watermark.sites import SITES

    extracted = REPO_ROOT / "data" / "extracted"
    offenders: list[str] = []
    examined = 0
    for path in sorted(extracted.rglob("*.yaml")):
        rel_segments = str(path.relative_to(extracted)).split("/")
        # Only the broad `*/<slug>` mechanism: a SECOND segment that is a (non-Lima) peer slug.
        if len(rel_segments) < 2 or rel_segments[1] not in SITES or rel_segments[1] == "lima":
            continue
        slug = rel_segments[1]
        examined += 1
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue  # schema validity is test_extracted_yaml_valid.py's job, not this one's
        if not isinstance(doc, dict):
            continue
        source = doc.get("source_path")
        source_rel = _documents_rel(source) if isinstance(source, str) else None
        if source_rel is None:
            continue  # nothing to corroborate against — narrow by design, like the sibling guard
        src = source_rel.split("/")
        attributed = src[0] == slug or (len(src) >= 2 and src[1] == slug)
        if not attributed:
            offenders.append(
                f"{path.relative_to(REPO_ROOT)} sits under `*/{slug}` (so Lima's build drops it) but "
                f"its source {source_rel} attributes elsewhere — a name collision, not {slug}'s record"
            )
    assert examined, "saw no `<collection>/<peer-slug>` extractions — the guard went vacuous"
    assert not offenders, (
        "`*/<slug>` subtracted an artifact from Lima on a name collision, not real attribution "
        "(#1405 review):\n" + "\n".join(offenders)
    )


def test_unscoped_sibling_loads_its_own_corpus_not_lima() -> None:
    """The read side honors the #780 scope: Urbana's corpus is bounded to its own extracted tree +
    its Highland55 land-assembly document prefixes (#1328), NOT Lima's whole tree. Urbana has no
    *extracted* deeds/permits/OPC-summaries (its Highland55 corpus is raw source documents), so the
    scoped read stays free of Lima's Allen-County extractions.
    Before #780 its ``None`` scope meant the whole tree, silently inheriting Allen County."""
    from watermark.pipeline.corpus import load_corpus

    urbana = load_corpus(Settings(site="urbana", data_dir=REPO_ROOT / "data"))
    assert not urbana.deeds, "Urbana must not inherit Lima's recorder deeds"
    assert not urbana.permits, "Urbana must not inherit Lima's NPDES permits"
    assert not urbana.summaries, "Urbana must not inherit Lima's OPC estimates"

    # Contrast: Lima (the reference build) still loads its full corpus.
    lima = load_corpus(Settings(site="lima", data_dir=REPO_ROOT / "data"))
    assert lima.deeds and lima.permits, "the reference build still reads the whole tree"


# --- #606: per-site reference YAML readers resolve the active site's path ---------------


def test_load_baseline_reads_fort_wayne_not_lima(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    fw = load_baseline(fw_settings)
    assert fw is not None
    assert fw.fips == "18003"  # Allen County, Indiana — not Lima's 39003 (Allen County, OH)
    assert "Indiana" in fw.area_name
    # The Lima reader still resolves Lima — the slug-scoped split is symmetric.
    lima = load_baseline(lima_settings)
    assert lima is not None and lima.fips == "39003"


def test_load_consumer_energy_reads_indiana(fw_settings: Settings) -> None:
    fw = load_consumer_energy(fw_settings)
    assert fw is not None
    assert fw.area == "IN" and fw.area_name == "Indiana"


def test_load_grid_profile_reads_fort_wayne_utility(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    fw = load_grid_profile(fw_settings)
    assert fw is not None
    assert "Indiana Michigan Power" in fw.serving_utility.utility.value
    assert "AEP Ohio" not in fw.serving_utility.utility.value
    lima = load_grid_profile(lima_settings)
    assert lima is not None and "AEP Ohio" in lima.serving_utility.utility.value


# --- #608: the FERC seam emits the active site's regulator / utility, not Ohio/PUCO/AEP --


def _seam_blob(settings: Settings) -> str:
    """Every cited string in the seam, flattened — so a leak anywhere is caught."""
    seam = derive_ferc_seam(settings=settings)
    b = seam.boundary
    parts = [
        b.ferc_scope.value,
        b.ferc_scope.citation,
        b.puco_scope.value,
        b.puco_scope.citation,
        b.campus_arrangement.value,
        b.campus_arrangement.citation,
        b.note,
        seam.form1.utility,
        seam.form1.pointer.value,
        seam.form1.pointer.citation,
        seam.note,
    ]
    return "\n".join(parts)


def test_ferc_seam_emits_indiana_iurc_not_ohio_puco(fw_settings: Settings) -> None:
    blob = _seam_blob(fw_settings)
    # The active site's regulator + serving utility.
    assert "IURC" in blob and "Indiana" in blob
    assert "Indiana Michigan Power" in blob
    # No Lima/Ohio leak anywhere in the seam.
    assert "PUCO" not in blob
    assert "Ohio" not in blob
    assert "AEP Ohio" not in blob
    # The Form-1 filer is I&M, not Ohio Power Company.
    seam = derive_ferc_seam(settings=fw_settings)
    assert "Indiana Michigan Power" in seam.form1.utility
    assert "Ohio Power Company" not in seam.form1.utility


def test_ferc_seam_still_correct_for_lima(lima_settings: Settings) -> None:
    blob = _seam_blob(lima_settings)
    assert "PUCO" in blob and "AEP Ohio" in blob and "Ohio Power Company" in blob
    assert "IURC" not in blob


# --- #607: the cooling basis takes the active facility's discharge, not Lima's FM-2 ------


def test_cooling_basis_does_not_leak_lima_fm2_for_other_site(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    # Fort Wayne's facility discloses no cooling/industrial blowdown (blowdown_mgd=None) — the high
    # bound must fall back to the site's own power-derived consumptive, never Lima's FM-2 (CMAR) figure.
    fw_high = derive_cooling_basis(settings=fw_settings).consumptive_high
    assert "CMAR" not in (fw_high.citation or "")
    assert "FM2" not in (fw_high.citation or "") and "FM-2" not in (fw_high.citation or "")
    assert "no disclosed blowdown" in (fw_high.citation or "")
    # Lima still traces its cross-check to the disclosed FM-2 discharge (per its facility).
    lima = derive_cooling_basis(settings=lima_settings)
    assert "CMAR" in (lima.consumptive_high.citation or "")
    assert lima.it_load.value == pytest.approx(275.0)
    assert "P0138965" in (lima.it_load.citation or "")  # traces to the active facility's permit


def test_power_basis_traces_to_the_active_facilitys_permit_not_lima(
    fw_settings: Settings, lima_settings: Settings
) -> None:
    # #360/#607: Fort Wayne's power basis (the first non-Lima facility) must carry ITS OWN IDEM
    # permit + derived figures, never Lima's hardcoded P0138965 / 313 MW / 114 x 2.75 MW.
    fw = derive_power_basis(settings=fw_settings)
    assert fw is not None and fw.it_load.value == pytest.approx(90.0)
    assert fw.backup_power.value == pytest.approx(102.0, abs=0.1)  # 34 x 3.0
    blob = (
        " ".join(str(getattr(fw, f).citation or "") for f in ("backup_power", "it_load"))
        + fw.cooling_overhead_note
        + fw.generation_note
        + fw.method
    )
    assert "003-47378" in (fw.it_load.citation or "")  # the IDEM Title V permit
    for lima_literal in ("P0138965", "313", "114 x", "2.75", "250-300"):
        assert lima_literal not in blob, f"Lima literal {lima_literal!r} leaked into Fort Wayne"
    # Lima still carries its own permit.
    lima = derive_power_basis(settings=lima_settings)
    assert lima is not None and "P0138965" in (lima.it_load.citation or "")
