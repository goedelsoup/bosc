"""Multi-hypothesis layer: the default set reproduces run_scenarios' buildout
numbers (regression lock), and Shawnee II's theorized FM-3 is held out unless a
hypothesis explicitly promotes it.
"""

from __future__ import annotations

from watermark.config import Settings
from watermark.hydrology import hypothesis as hyp_stage
from watermark.pipeline import hydrology as hydro_stage


def test_default_buildout_matches_run_scenarios(hydro_settings: Settings) -> None:
    """`buildout-confirmed` must equal run_scenarios' buildout net loss (no drift)."""
    _, build, _ = hydro_stage.run_scenarios(settings=hydro_settings, live=False)
    comparison = hyp_stage.run_hypotheses(settings=hydro_settings, live=False)
    confirmed = next(h for h in comparison.hypotheses if h.hypothesis.name == "buildout-confirmed")
    assert confirmed.result.consumptive_loss.value == build.consumptive_loss.value


def test_shawnee_held_out_unless_promoted(hydro_settings: Settings) -> None:
    comparison = hyp_stage.run_hypotheses(settings=hydro_settings, live=False)
    by_name = {h.hypothesis.name: h for h in comparison.hypotheses}

    # Default confirmed routing holds Shawnee II's FM-3 out.
    confirmed = by_name["buildout-confirmed"]
    assert any("shawnee" in r.via.lower() for r in confirmed.excluded_theorized)
    assert all("shawnee" not in r.via.lower() for r in confirmed.routing_applied)

    # The what-if promotes it: Shawnee II joins the built routes, nothing held out.
    fm3 = by_name["buildout-with-fm3"]
    assert any("shawnee" in r.via.lower() for r in fm3.routing_applied)
    assert not fm3.excluded_theorized


def test_level_is_carried(hydro_settings: Settings) -> None:
    comparison = hyp_stage.run_hypotheses(settings=hydro_settings, live=False)
    assert {h.hypothesis.level for h in comparison.hypotheses} == {"site"}


def test_comparison_is_yaml_serializable(hydro_settings: Settings) -> None:
    """`hydro-hypotheses --write` safe-dumps the comparison; a bare model_dump() leaves a
    ``CoolingModelType`` enum that ``yaml.safe_dump`` cannot represent, so the CLI dumps with
    ``mode="json"``. Lock that the comparison round-trips to YAML with the enum as its scalar.
    """
    import yaml

    comparison = hyp_stage.run_hypotheses(settings=hydro_settings, live=False)
    text = yaml.safe_dump(comparison.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    assert "cooling_model" in text
    assert "CoolingModelType" not in text  # serialized to its value ("off"/…), not the enum repr
    yaml.safe_load(text)  # round-trips without error
