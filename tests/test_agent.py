"""Tests for the agent layer: in-process tools and result aggregation.

The Claude Agent SDK ``query`` is monkeypatched, so nothing here spawns the CLI
or hits the network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from watermark.agent import client as client_mod
from watermark.agent import tools, yidam_tools
from watermark.agent.client import DEFAULT_SYSTEM_PROMPT, RESEARCH_SKILLS, ResearchAgent
from watermark.agent.extractor import StructuredExtractor
from watermark.config import Settings
from watermark.models import Estimate, PageExtraction
from watermark.pipeline.extract import save_extraction
from watermark.tasks import PipelineTask

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- tools -----------------------------------------------------------------
async def test_program_overview_reads_committed_summary() -> None:
    out = await tools.program_overview.handler({})
    text = out["content"][0]["text"]
    assert "Program construction total" in text
    assert "Diller" in text  # one of the sub-estimates
    assert "checks pass" in text


async def test_reference_tools_do_not_serve_lima_data_off_home(
    monkeypatch: pytest.MonkeyPatch,
    hydro_settings: Settings,
) -> None:
    # #424: a per-site run must NOT be silently handed Lima's reference record.
    # timeline/entities now serve the active site's own corpus (per-site scoped via
    # load_corpus()) rather than returning a _reference_only notice. Findlay committed its
    # own flood-mitigation record set (#1465: the FEMA FMA obligation + the USACE feasibility
    # Review Plan), so these tools return FINDLAY's own events/entities, NOT Lima's cross-site
    # record. hydrology_balance runs per-site only for sites that committed their own
    # watch-items.geojson (#829) — and since #1265 Findlay HAS one, so it now serves Findlay's
    # own balance instead of the notice. That is the stronger form of this test's guarantee,
    # not a weakening of it: the tool answers from this site's WPCC, and Lima's periplus WWTP
    # graph must not appear anywhere in the answer.
    # Offline hydrology settings (the `hydro_settings` wiring + this slug): now that Findlay has
    # a committed watch-items graph, `hydrology_balance` really runs its balance here, and the
    # suite is hermetic — no connector call may reach the network (tests/CLAUDE.md).
    findlay_settings = hydro_settings.model_copy(update={"site": "findlay"})
    monkeypatch.setattr(tools, "get_settings", lambda: findlay_settings)

    # hydrology_balance serves FINDLAY's own committed WWTP graph — its one permitted
    # discharger, screened against its own cited at-outfall design low flow.
    hydro_text = (await tools.hydrology_balance.handler({}))["content"][0]["text"]
    assert hydro_text.startswith("[scope]") and "findlay" in hydro_text
    assert "Findlay WPCC" in hydro_text
    assert "Blanchard River (Findlay WPCC outfall, RM 56.42)" in hydro_text
    # Lima's periplus plants are the thing that must never bleed through here (#424/#829).
    for lima_plant in ("Lima WWTP", "American II", "American Bath", "Shawnee II"):
        assert lima_plant not in hydro_text

    # entities and timeline now serve findlay's OWN flood corpus (#1465), not Lima's — so
    # Lima-specific records must not leak through.
    entities_text = (await tools.entities.handler({}))["content"][0]["text"]
    assert "No entities found" in entities_text or "ENTITIES:" in entities_text
    # The Lima reference graph has Amazon / Google / permit holders — must not appear.
    assert "Amazon" not in entities_text and "Google" not in entities_text

    # Findlay's timeline is scoped to its own committed corpus and carries its own flood
    # events (the FEMA/USACE agency actions, tagged [epa_permit_action]), not Lima's.
    timeline_text = (await tools.timeline.handler({}))["content"][0]["text"]
    assert timeline_text.startswith("[scope]") and "findlay" in timeline_text
    assert "[epa_permit_action]" in timeline_text
    # Lima's commissioners minutes must not bleed into a Findlay run — but "commissioners" is no
    # longer a usable proxy for that. Since #1839 Findlay has ingested a body of its own by that
    # name (Hancock County's board, which Lima's registry deliberately excludes for Allen County),
    # so the word appears legitimately. Test the thing the proxy stood for: every meeting event
    # cited here comes from Findlay's OWN nested tree, never Lima's flat `commissioners/`.
    assert "findlay/hancock-county-commissioners/meetings/" in timeline_text
    assert "<commissioners/" not in timeline_text
    assert "commissioners/minutes/" not in timeline_text

    # list_documents filters data/documents/ by the site's own corpus scope rather than
    # returning a _reference_only notice. Since #1460 Findlay owns real source bytes in TWO
    # collections — its NPDES instrument set under `oepa/findlay/` and the WARN/brownfield
    # instruments under `findlay/` — so this serves Findlay's own documents and, critically,
    # none of Lima's.
    docs_text = (await tools.list_documents.handler({}))["content"][0]["text"]
    assert "2PD00008.fs.pdf" in docs_text and "GoodyearTireRubberCompany.pdf" in docs_text
    # Lima's own collections must not bleed into a Findlay run.
    assert "2PE00000.pdf" not in docs_text and "PRR-01-bundle" not in docs_text

    # program_overview resolves within findlay's own corpus (which has no OPC estimate) —
    # no Lima OPC leak.
    po = (await tools.program_overview.handler({}))["content"][0]["text"]
    assert "Program construction total" not in po

    # Zero-drift for the corpus home: no banner, and the real Lima data.
    monkeypatch.setattr(
        tools, "get_settings", lambda: Settings(site="lima", data_dir=REPO_ROOT / "data")
    )
    home = (await tools.program_overview.handler({}))["content"][0]["text"]
    assert not home.startswith("[scope]") and "Program construction total" in home


async def test_hydrology_balance_populated_for_site_with_watch_items(
    hydro_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #829: troy-piqua committed its own watch-items.geojson (Piqua WWTP) + a cited
    # receiving-water 7Q10, so hydrology_balance runs per-site instead of returning the
    # reference-only stub — and it must carry NONE of Lima's WWTP graph or forcemain caveats.
    # Reuse the hermetic hydro_settings fixture (offline + committed hydro_fixtures_dir),
    # overriding only the site (tests/CLAUDE.md).
    settings = hydro_settings.model_copy(update={"site": "troy-piqua"})
    monkeypatch.setattr(tools, "get_settings", lambda: settings)
    text = (await tools.hydrology_balance.handler({}))["content"][0]["text"]

    # Not the reference-only stub; the real Piqua balance + assimilative screen is present.
    assert "No committed hydrology_balance" not in text
    assert "Piqua WWTP" in text and "Upper Great Miami River" in text
    # The cited GMR-above-Sidney 7Q10 (24.0 cfs) screens the 13.46 cfs design discharge to a
    # 1.78:1 chronic dilution (24.00 / 13.46), and the cited 1Q10 (19.4 cfs) to a 1.44:1 acute
    # ratio (WS-08) — assert the full computed line so a miscomputed ratio fails.
    assert (
        "Upper Great Miami River 7Q10 24.00 cfs vs discharge 13.46 cfs -> 1.78:1 chronic dilution"
        in text
    )
    assert "acute 1Q10 19.40 cfs -> 1.44:1" in text
    # No Lima bleed: no Ottawa/Shawnee/American WWTPs, no BOSC campus node or FM routing caveat.
    for leak in ("Shawnee II", "American", "Ottawa River", "BOSC data-center campus", "FM-3"):
        assert leak not in text


async def test_extraction_tools_scope_to_the_active_sites_subtree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #424: list_extractions / read_extraction resolve the ACTIVE site's own subtree, never
    # another site's. A Lima-tree file must not leak into a findlay run's listing.
    settings = Settings(site="findlay", data_dir=tmp_path)
    site_dir = settings.extracted_dir / "findlay"
    site_dir.mkdir(parents=True)
    (site_dir / "deed.yaml").write_text("x: 1\n", encoding="utf-8")
    (settings.extracted_dir / "recorder").mkdir(parents=True)
    (settings.extracted_dir / "recorder" / "lima-deed.yaml").write_text("y: 2\n", encoding="utf-8")
    monkeypatch.setattr(tools, "get_settings", lambda: settings)

    listing = (await tools.list_extractions.handler({}))["content"][0]["text"]
    assert "deed.yaml" in listing and "lima-deed.yaml" not in listing
    assert listing.startswith("[scope]") and "findlay" in listing
    got = (await tools.read_extraction.handler({"filename": "deed.yaml"}))["content"][0]["text"]
    assert "x: 1" in got


async def test_extraction_tools_reach_collection_prefixed_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #1504: a peer whose corpus_relpaths name a collection prefix (Fort Wayne's
    # `idem/fort-wayne`) can list/read those records too — not just its bare `<slug>/` subdir —
    # and still never picks up another site's subtree or Lima's un-slugged collections.
    settings = Settings(
        site="fort-wayne", data_dir=tmp_path
    )  # scope ("fort-wayne", "idem/fort-wayne")
    (settings.extracted_dir / "fort-wayne").mkdir(parents=True)
    (settings.extracted_dir / "fort-wayne" / "wwtp.yaml").write_text("a: 1\n", encoding="utf-8")
    (settings.extracted_dir / "idem" / "fort-wayne").mkdir(parents=True)
    (settings.extracted_dir / "idem" / "fort-wayne" / "wqc.yaml").write_text(
        "permit: WQC\n", encoding="utf-8"
    )
    # Out-of-scope neighbours.
    (settings.extracted_dir / "recorder").mkdir(parents=True)
    (settings.extracted_dir / "recorder" / "lima-deed.yaml").write_text("y: 2\n", encoding="utf-8")
    monkeypatch.setattr(tools, "get_settings", lambda: settings)

    listing = (await tools.list_extractions.handler({}))["content"][0]["text"]
    assert "fort-wayne/wwtp.yaml" in listing
    assert "idem/fort-wayne/wqc.yaml" in listing  # the #1504 record, previously invisible
    assert "lima-deed.yaml" not in listing
    # read by the full data/extracted-relative key as printed…
    by_rel = (await tools.read_extraction.handler({"filename": "idem/fort-wayne/wqc.yaml"}))[
        "content"
    ][0]["text"]
    assert "permit: WQC" in by_rel
    # …and by bare basename.
    by_name = (await tools.read_extraction.handler({"filename": "wqc.yaml"}))["content"][0]["text"]
    assert "permit: WQC" in by_name
    # an out-of-scope file stays unreachable.
    miss = (await tools.read_extraction.handler({"filename": "lima-deed.yaml"}))["content"][0][
        "text"
    ]
    assert miss.startswith("Not found")


async def test_reconcile_estimate_rejects_non_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    settings.extracted_dir.mkdir(parents=True)
    # A file not in the generated (top-level `estimate:`) shape.
    (settings.extracted_dir / "foo.opc.yaml").write_text("sub_estimates: []\n")
    monkeypatch.setattr(tools, "get_settings", lambda: settings)
    out = await tools.reconcile_estimate.handler({"filename": "foo.opc.yaml"})
    assert "not a generated estimate extraction" in out["content"][0]["text"]


async def test_reconcile_estimate_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(tools, "get_settings", lambda: settings)
    estimate = Estimate.model_validate(
        {
            "name": "Test Roundabout",
            "sections": [
                {
                    "name": "ROADWAY",
                    "subtotal": 21500,
                    "line_items": [
                        {"description": "a", "total_amount": 20000},
                        {"description": "b", "total_amount": 1500},
                    ],
                },
            ],
            "construction_subtotal": 21500,
            "markups": [{"label": "Contingency", "rate": 0.25, "amount": 5375}],
            "total": 26875,
        }
    )
    path = save_extraction(
        PageExtraction(
            doc_id="d", source_path="/x", page_index=0, pdf_page=1, dpi=300, estimate=estimate
        ),
        settings=settings,
    )
    out = await tools.reconcile_estimate.handler({"filename": path.name})
    text = out["content"][0]["text"]
    assert "line-item-rollup" in text
    assert "XX" not in text  # everything ties out


# --- agent configuration: discipline prompt + skills (#247) ----------------
def test_options_wire_the_discipline_prompt_and_research_skills() -> None:
    opts = ResearchAgent()._options()
    # The discipline prompt replaced the stale "roadwork program" framing.
    assert "roadwork program" not in opts.system_prompt
    assert "Evidentiary discipline is the organizing constraint" in opts.system_prompt
    # The read-only research skill subset, loaded from the project's .claude/skills/.
    assert opts.skills == RESEARCH_SKILLS
    assert opts.setting_sources == ["project"]
    # Setting `skills` lets the SDK add the `Skill` tool itself — our allowlist stays the
    # read-only BOSC tools (no Bash/Write/etc. leak in). #1563 appends the yidam corpus-mirror
    # backend's `mcp__yidam__*` tools (enabled by default).
    assert opts.allowed_tools == tools.ALLOWED_TOOL_NAMES + yidam_tools.ALLOWED_TOOL_NAMES
    assert len(tools.ALLOWED_TOOL_NAMES) == 25  # +search_web, +fetch_url (#1048)
    # The yidam half is DERIVED from the frozen contract rather than counted. A literal count
    # went stale the moment the contract grew from 5 tools to 13 (#2126) and reported only
    # `8 != 5`, which names nothing.
    #
    # What this catches is narrower than "which tool appeared or vanished", and worth stating
    # so nobody trusts it for more: a tool ADDED upstream with no handler is a `KeyError` at
    # import, before this test runs, and one REMOVED leaves both sides at once. It catches a
    # handler bound to the wrong `_HANDLERS` key — each `@tool` takes its name from the
    # contract spec, so a mis-keyed entry makes the two lists disagree in ORDER or CONTENT
    # while both stay the same length.
    served = [f"mcp__yidam__{name}" for name in yidam_tools.served_tool_names()]
    assert served == yidam_tools.ALLOWED_TOOL_NAMES
    # The half the derivation cannot see: every handler answers to the name it is filed under.
    assert [t.name for t in yidam_tools.ALL_TOOLS] == yidam_tools.served_tool_names()
    assert "data-center-sweep" in RESEARCH_SKILLS  # +data-center-sweep (#1049)


def test_yidam_backend_wires_a_second_server_and_can_be_disabled() -> None:
    # #1563: the yidam corpus-mirror backend is a second in-process MCP server, on by default.
    opts = ResearchAgent()._options()
    assert set(opts.mcp_servers) == {tools.SERVER_NAME, yidam_tools.YIDAM_SERVER_NAME}
    # Bare names — the server is already namespaced by its own name (`mcp__yidam__*`), which
    # is why the frozen contract drops the redundant `yidam_` prefix.
    assert opts.allowed_tools[-1] == "mcp__yidam__neighbors"
    assert "mcp__yidam__retrieve" in opts.allowed_tools

    # enable_yidam=False drops the server + its tools, leaving only the base BOSC tools.
    bare = ResearchAgent(enable_yidam=False)._options()
    assert set(bare.mcp_servers) == {tools.SERVER_NAME}
    assert bare.allowed_tools == tools.ALLOWED_TOOL_NAMES

    # enable_tools=False drops both servers entirely.
    none = ResearchAgent(enable_tools=False)._options()
    assert none.mcp_servers is None or none.mcp_servers == {}


def test_per_task_key_routes_into_the_agent_subprocess_env() -> None:
    # #1080: the ASK agent's calls go out on the ask-workspace key, injected via the SDK's
    # `env` (which merges over the inherited process env, so only ANTHROPIC_API_KEY changes).
    settings = Settings.model_validate({"ANTHROPIC_API_KEY": "base", "anthropic_key_ask": "k-ask"})
    opts = ResearchAgent(settings=settings)._options()
    assert opts.env == {"ANTHROPIC_API_KEY": "k-ask"}


def test_agent_falls_back_to_the_base_key_when_no_task_key_is_set() -> None:
    settings = Settings.model_validate({"ANTHROPIC_API_KEY": "base"})
    assert ResearchAgent(settings=settings)._options().env == {"ANTHROPIC_API_KEY": "base"}
    # With no key at all, `env` is left unset so ambient auth (e.g. a session token) is untouched.
    assert not ResearchAgent(settings=Settings.model_validate({}))._options().env


def test_agent_normalizes_an_unknown_task_instead_of_raising_mid_turn() -> None:
    # #1080: `task` is normalized once in __init__, so a bad string never reaches the
    # `.value` access in converse() (which used to construct PipelineTask(self.task) live).
    agent = ResearchAgent(settings=Settings.model_validate({}), task="not-a-task")
    assert agent.task is PipelineTask.ASK  # falls back to the default, like anthropic_key_for
    assert agent.task.value == "ask"  # safe for the trace attribute
    # A valid string still round-trips to its member.
    assert (
        ResearchAgent(settings=Settings.model_validate({}), task="draft").task is PipelineTask.DRAFT
    )


def test_extractor_selects_its_task_key() -> None:
    # #1080: the extractor builds its Anthropic client with the per-task workspace key.
    settings = Settings.model_validate(
        {"ANTHROPIC_API_KEY": "base", "anthropic_key_extract": "k-ext"}
    )
    assert StructuredExtractor(settings=settings).client.api_key == "k-ext"
    # A DRAFT-tagged extractor (the research distill pass) picks its own key.
    draft_settings = Settings.model_validate(
        {"ANTHROPIC_API_KEY": "base", "anthropic_key_draft": "k-draft"}
    )
    assert (
        StructuredExtractor(settings=draft_settings, task=PipelineTask.DRAFT).client.api_key
        == "k-draft"
    )


def test_held_back_skills_are_not_active() -> None:
    # The authoring/legal/production skills stay out of the read-only research surface.
    for held in (
        "investigative-writing-and-editorial",
        "public-records-and-legal-strategy",
        "document-production-and-ocr",
    ):
        assert held not in RESEARCH_SKILLS


def test_system_prompt_asset_mirrors_the_method_doc() -> None:
    # The packaged runtime prompt and the investigative-method doc must not drift.
    doc = (REPO_ROOT / "docs" / "investigative-method" / "SYSTEM_PROMPT.md").read_text(
        encoding="utf-8"
    )
    doc_body = doc.split("\n---\n", 1)[1].strip()
    assert doc_body == DEFAULT_SYSTEM_PROMPT.strip()


# --- ResearchAgent.converse ------------------------------------------------
async def _fake_query(*, prompt: str, options: Any):  # type: ignore[no-untyped-def]
    yield AssistantMessage(content=[TextBlock(text="Looking at the estimates. ")], model="m")
    yield AssistantMessage(
        content=[ToolUseBlock(id="t1", name="mcp__bosc__program_overview", input={})], model="m"
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=8,
        is_error=False,
        num_turns=2,
        session_id="s",
        total_cost_usd=0.0123,
        result="The Diller roundabout.",
    )


async def test_converse_aggregates_answer_tools_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "query", _fake_query)
    agent = ResearchAgent()
    streamed: list[str] = []

    result = await agent.converse("which roundabout?", on_text=streamed.append)

    assert result.text == "The Diller roundabout."  # prefers ResultMessage.result
    assert result.tools_used == ["mcp__bosc__program_overview"]
    assert result.num_turns == 2
    assert result.cost_usd == 0.0123
    assert result.is_error is False
    assert "Looking at the estimates. " in "".join(streamed)  # streamed live
