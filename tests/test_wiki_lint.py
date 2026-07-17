"""The wiki cross-link audit — ``watermark wiki-lint`` (#1571, epic #1560 · C).

The audit rebuilds the ``[[wiki link]]`` cross-reference graph the frontend renders (resolved
concept/person body links + ``related:`` slugs, over the same site-scoped concepts / entities /
people) and flags the three gaps: unresolved links (the hard gate), orphan concepts, and
under-linked concepts. These pin the resolution index (faithful to ``web/.../wiki.ts``), the
graph degrees, the gate, the ``--suggest`` hints, and a clean pass over the real Lima corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from watermark.cli import app
from watermark.config import Settings
from watermark.site.corpus_mirror import MirrorFeeds
from watermark.site.feeds import ConceptItem, EntityNode, PersonItem
from watermark.site.wiki_lint import (
    audit_wiki,
    build_wiki_index,
    lint_wiki,
    norm,
    render_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
runner = CliRunner()


# --- a small synthetic corpus --------------------------------------------------------------
def _feeds(**overrides: object) -> MirrorFeeds:
    concepts = [
        # links out to a sibling concept, an entity, and a person; `related` echoes the sibling
        ConceptItem(
            slug="alpha",
            title="Alpha",
            body="See [[Beta]], [[Gamma Entity]], and [[Jane Doe]]. The Delta program is separate.",
            related=["beta"],
        ),
        ConceptItem(slug="beta", title="Beta", body="Refers to [[Alpha]].", related=["alpha"]),
        # an unresolved BODY link + an unresolved `related` slug
        ConceptItem(
            slug="gamma",
            title="Gamma",
            body="Mentions [[Nonexistent Term]].",
            related=["missing-slug"],
        ),
        # nothing in, nothing out → orphan + under-linked
        ConceptItem(slug="delta", title="Delta", body="", related=[]),
    ]
    entities = [
        EntityNode(
            key="GAMMA", display="Gamma Entity", kind="corporate", classification="operator"
        ),
    ]
    people = [PersonItem(slug="jane-doe", name="Jane Doe", summary="A principal.")]
    kwargs: dict[str, object] = {
        "site": "lima",
        "site_label": "Lima, Ohio",
        "site_detail": "",
        "entities": entities,
        "relationships": [],
        "concepts": concepts,
        "people": people,
        "leads": [],
        "open_claims": [],
    }
    kwargs.update(overrides)
    return MirrorFeeds(**kwargs)  # type: ignore[arg-type]


# --- norm + the resolution index -----------------------------------------------------------
def test_norm_matches_the_frontend_semantics() -> None:
    # lowercase, non-alnum runs → single space, trimmed (the wiki.ts `norm`)
    assert norm("7Q10") == "7q10"
    assert norm("Ohio EPA") == "ohio epa"
    assert norm("  Total-Phosphorus!! ") == "total phosphorus"


def test_index_keys_every_name_first_writer_wins() -> None:
    index = build_wiki_index(
        [ConceptItem(slug="gamma", title="Gamma", aliases=["G-node"])],
        [EntityNode(key="GAMMA", display="Gamma Entity", kind="x", classification="y")],
        [PersonItem(slug="jane-doe", name="Jane Doe")],
    )
    # concept keyed by slug, title, alias
    assert index["gamma"].id == "concept:gamma"
    assert index["g node"].id == "concept:gamma"
    # the entity's `key` also normalizes to "gamma" — but the concept was inserted first and wins
    assert index["gamma"].kind == "concept"
    # the entity is still reachable by its display; the person by their name
    assert index["gamma entity"].id == "entity:GAMMA"
    assert index["jane doe"].id == "person:jane-doe"


# --- the audit -----------------------------------------------------------------------------
def test_audit_resolves_links_to_concepts_entities_and_people() -> None:
    report = audit_wiki(_feeds(), min_degree=2)
    # 4 concepts; scanned = alpha(3 body + 1 related) + beta(1+1) + gamma(1+1) + delta(0) = 8
    assert report.concepts == 4
    assert report.links_scanned == 8


def test_audit_flags_unresolved_body_and_related_links() -> None:
    report = audit_wiki(_feeds())
    kinds = {(u.source_id, u.via, u.target) for u in report.unresolved}
    assert ("concept:gamma", "body", "Nonexistent Term") in kinds
    assert ("concept:gamma", "related", "missing-slug") in kinds
    assert len(report.unresolved) == 2
    # the body link carries its 1-based line; the related slug has none
    body = next(u for u in report.unresolved if u.via == "body")
    assert body.line == 1
    assert not report.ok  # the gate fails on any unresolved link


def test_audit_flags_orphan_and_underlinked_concepts() -> None:
    report = audit_wiki(_feeds(), min_degree=2)
    orphans = {o.id for o in report.orphans}
    # gamma (in 0) and delta (in 0) have nobody linking to them; alpha/beta are linked
    assert orphans == {"concept:gamma", "concept:delta"}
    underlinked = {u.id for u in report.underlinked}
    assert underlinked == {"concept:gamma", "concept:delta"}
    # alpha is well-connected: out to beta/entity/person (3) + in from beta (1)
    assert "concept:alpha" not in underlinked


def test_self_links_do_not_count_as_degree() -> None:
    feeds = _feeds(
        concepts=[ConceptItem(slug="solo", title="Solo", body="I am [[Solo]].", related=["solo"])],
        entities=[],
        people=[],
    )
    report = audit_wiki(feeds, min_degree=1)
    # the concept links only to itself → still orphan + under-linked, never self-satisfied
    assert {o.id for o in report.orphans} == {"concept:solo"}
    assert {u.id for u in report.underlinked} == {"concept:solo"}


def test_a_fully_connected_pair_is_clean() -> None:
    feeds = _feeds(
        concepts=[
            ConceptItem(slug="a", title="A", body="[[B]]", related=["b"]),
            ConceptItem(slug="b", title="B", body="[[A]]", related=["a"]),
        ],
        entities=[],
        people=[],
    )
    report = audit_wiki(feeds, min_degree=2)
    assert report.ok
    assert report.orphans == [] and report.underlinked == []


# --- suggestions (--suggest) ---------------------------------------------------------------
def test_suggest_proposes_an_incoming_link_for_an_orphan() -> None:
    # Alpha's prose names "Delta" in plain text (not linked); Delta is an orphan → suggest it.
    report = audit_wiki(_feeds(), min_degree=2, suggest=True)
    proposed = {(s.source_id, s.target.id, s.helps) for s in report.suggestions}
    assert ("concept:alpha", "concept:delta", "orphan-target") in proposed


def test_suggest_is_empty_without_the_flag() -> None:
    assert audit_wiki(_feeds(), suggest=False).suggestions == []


def test_suggest_ignores_already_linked_targets() -> None:
    # Alpha already links [[Beta]] in prose, so Beta is never re-suggested to Alpha.
    report = audit_wiki(_feeds(), suggest=True)
    assert not any(
        s.source_id == "concept:alpha" and s.target.id == "concept:beta" for s in report.suggestions
    )


# --- rendering -----------------------------------------------------------------------------
def test_render_report_names_each_section() -> None:
    text = render_report(audit_wiki(_feeds(), suggest=True), suggest=True)
    assert "unresolved [[wiki links]] (2)" in text
    assert "orphan concepts (2)" in text
    assert "gate: FAIL" in text


def test_render_report_clean() -> None:
    feeds = _feeds(
        concepts=[
            ConceptItem(slug="a", title="A", body="[[B]]", related=["b"]),
            ConceptItem(slug="b", title="B", body="[[A]]", related=["a"]),
        ],
        entities=[],
        people=[],
    )
    text = render_report(audit_wiki(feeds, min_degree=2))
    assert "all clean" in text


# --- integration: the real committed Lima corpus -------------------------------------------
def test_lima_corpus_has_no_unresolved_wiki_links() -> None:
    """The hard gate must pass over the real committed corpus — no broken cross-links ship."""
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    report = lint_wiki(settings, min_degree=2)
    assert report.concepts > 0
    assert report.links_scanned > 0
    assert report.unresolved == [], [(u.source_id, u.line, u.target) for u in report.unresolved]
    assert report.ok


@pytest.mark.parametrize("site", ["fort-wayne", "urbana"])
def test_selectable_peer_sites_are_also_clean(site: str) -> None:
    """A concept body must not link a Lima-only concept absent from a peer's scoped feed."""
    settings = Settings(data_dir=REPO_ROOT / "data", site=site)
    report = lint_wiki(settings, min_degree=2)
    assert report.ok, [(u.source_id, u.target) for u in report.unresolved]


# --- the CLI -------------------------------------------------------------------------------
def test_cli_clean_exits_zero() -> None:
    result = runner.invoke(app, ["--site", "lima", "wiki-lint"])
    assert result.exit_code == 0, result.output
    assert "wiki-lint clean" in result.output


def test_cli_fails_on_an_unresolved_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "foo.md").write_text(
        "---\ntitle: Foo\n---\nA body that links [[Does Not Exist]].\n", encoding="utf-8"
    )
    settings = Settings(data_dir=tmp_path, site="lima")
    monkeypatch.setattr("watermark.cli.wiki.get_settings", lambda: settings)

    result = runner.invoke(app, ["wiki-lint"])
    assert result.exit_code == 1, result.output
    assert "unresolved" in result.output
    # --no-check reports the same gap but does not fail the process
    ok = runner.invoke(app, ["wiki-lint", "--no-check"])
    assert ok.exit_code == 0, ok.output


def test_cli_writes_a_report_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    monkeypatch.setattr("watermark.cli.wiki.get_settings", lambda: settings)
    out = tmp_path / "wiki-lint.txt"

    result = runner.invoke(app, ["wiki-lint", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "wiki-lint · lima" in out.read_text(encoding="utf-8")
