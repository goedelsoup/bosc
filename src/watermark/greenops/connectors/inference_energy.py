"""LLM inference-energy coefficients — the factor table that puts inference in the chain (#1643/F2).

For a Claude-driven platform, model inference is plausibly the largest energy component, yet
it entered the footprint only as a display "call count": there was no Wh-per-token coefficient
anywhere, so the electricity / carbon / water headlines structurally could not represent it.
This is the missing table.

**It is a curated `reference` table, not a pull, and that is not laziness.** No model provider
publishes a per-token energy figure for its hosted models — Anthropic does not, and the Admin
API exposes tokens and dollars only. What exists is *third-party measurement and modeling*,
which is what these rows transcribe, each with a dated citation.

**Every row is banded, because the published spread is the finding.** Estimates of the same
quantity differ by roughly an order of magnitude, mostly by *boundary*: an accelerator-only
figure counts the GPU seconds, an infrastructure-aware figure adds host CPU/DRAM, idle
capacity, and facility overhead. Google's own measurement (2025-08) found the accelerator is
**58%** of full-stack energy — so a narrow-boundary number is not merely uncertain, it is
low by construction. A consumer that drops the band overstates what is known.

**Basis matters as much as magnitude.** Decode (output-token generation) is
memory-bandwidth-bound and dominates inference energy; prefill (input) is far cheaper per
token. Every coefficient here is priced per 1,000 **output** tokens, and the derivation must
apply it to output tokens only — applying an output-basis coefficient to an input+output
total would overstate energy several-fold on a cache-heavy agentic workload like ours.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.greenops.model import InferenceEnergyBenchmark, InferenceEnergyTable
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

INFERENCE_ENERGY_VINTAGE = "Epoch AI 2025-02 / Jegham et al. 2025-05 / Google 2025-08"

# The published anchors these rows are built from, all measured or modeled per *query* and
# converted here to a per-1k-output-token basis at each source's own stated token count:
#
#   * Epoch AI (2025-02), "How much energy does ChatGPT use?" — ~0.3 Wh for a typical GPT-4o
#     query at an explicit 500-output-token basis => 0.6 Wh / 1k output tokens. Accelerator +
#     host; excludes facility overhead. This is the LOW anchor, and the only source that
#     states its token count outright, which is why it sets the central mid-tier value.
#   * Google (2025-08), arXiv:2508.15734 — 0.24 Wh for the median Gemini Apps text prompt,
#     measured full-stack in production; the active accelerator is only 58% of that total.
#     Corroborates the low anchor's order of magnitude at a *wider* boundary.
#   * Jegham, Abdelatti et al. (2025-05), arXiv:2505.09598, "How Hungry is AI?" —
#     infrastructure-aware benchmarking across 30 hosted models: Claude Sonnet ~0.8 Wh
#     (short) / 2.8 Wh (medium) / 5.5 Wh (long) per query, with the heaviest reasoning models
#     above 29 Wh on a long prompt. The paper does not publish per-query token counts, so it
#     is used to set the HIGH bound (roughly an order of magnitude above the accelerator-only
#     anchors) rather than a central value.
#
# Frontier vs mid-tier: no published per-token figure exists for Opus-class models
# specifically. The frontier row is therefore the mid-tier band scaled, and says so — it is a
# stated modeling choice inside a `reference` table, kept low-confidence and widely banded
# rather than presented as a measurement.
_ROWS: list[dict[str, Any]] = [
    {
        "model_class": "frontier",
        "label": "Frontier / reasoning-class hosted model",
        "value": 2.0,
        "low": 0.6,
        "high": 12.0,
        "confidence": "low",
        "cite": "No published per-token figure exists for Opus-class models; this is the "
        "mid-tier band scaled for a larger model and longer reasoning traces. Anchors: "
        "Epoch AI 2025-02 (~0.3 Wh / 500 output tokens, GPT-4o, accelerator+host) at the "
        "low bound; Jegham et al. 2025-05 (arXiv:2505.09598) infrastructure-aware per-query "
        "figures, where the heaviest reasoning models exceed 29 Wh on a long prompt, at the "
        "high bound.",
        "note": "The conservative default for an unmapped model id — an unrecognized model "
        "is priced high rather than dropped from the energy chain.",
    },
    {
        "model_class": "mid_tier",
        "label": "Mid-tier hosted model (Sonnet / GPT-4o class)",
        "value": 0.6,
        "low": 0.3,
        "high": 6.0,
        "confidence": "low",
        "cite": "Epoch AI, 'How much energy does ChatGPT use?' (2025-02): ~0.3 Wh per "
        "typical GPT-4o query at an explicit 500-output-token basis => 0.6 Wh per 1k output "
        "tokens (accelerator + host, excludes facility overhead). Corroborated at a wider "
        "boundary by Google, arXiv:2508.15734 (2025-08): 0.24 Wh for the median Gemini Apps "
        "text prompt measured full-stack. High bound from Jegham et al., arXiv:2505.09598 "
        "(2025-05), which measures Claude Sonnet at 0.8-5.5 Wh per query "
        "infrastructure-aware — roughly an order of magnitude above the accelerator-only "
        "anchors.",
        "note": "The best-attested row: the only anchor that states its own token basis.",
    },
    {
        "model_class": "small",
        "label": "Small / task-tuned hosted model",
        "value": 0.15,
        "low": 0.05,
        "high": 0.6,
        "confidence": "low",
        "cite": "Scaled below the mid-tier anchor (Epoch AI 2025-02) in proportion to served "
        "parameter count; Google (arXiv:2508.15734, 2025-08) reports a 33x year-over-year "
        "energy reduction for the median Gemini text prompt, so a small distilled model an "
        "order of magnitude under the mid-tier figure is consistent with the published "
        "trend. No direct measurement.",
        "note": "Not currently exercised — the platform's extraction workload runs on "
        "mid-tier models. Present so a right-sizing change is priced rather than untracked.",
    },
]

# Provider model id (longest matching prefix) -> model_class. Point releases resolve through
# their family prefix, so a dated id like `claude-opus-4-8-20260115` needs no new entry. An
# id matching nothing falls to `default_class` (frontier — the conservative direction).
_MODEL_CLASSES: dict[str, str] = {
    "claude-opus": "frontier",
    "claude-sonnet": "mid_tier",
    "claude-haiku": "small",
    "claude-3-opus": "frontier",
    "claude-3-sonnet": "mid_tier",
    "claude-3-haiku": "small",
}


def build_inference_energy_table() -> InferenceEnergyTable:
    """The committed inference-energy table, assembled from the in-code canonical.

    Every figure is ``reference`` (a published third-party estimate) and carries a band; the
    derivation that applies them stays ``derived``. Mirrors :func:`build_wue_table` — an
    in-code canonical emitted to YAML so it is regenerable and schema-checked rather than an
    orphaned hand-edited file.
    """
    return InferenceEnergyTable(
        vintage=INFERENCE_ENERGY_VINTAGE,
        benchmarks=[
            InferenceEnergyBenchmark(
                model_class=str(r["model_class"]),
                label=str(r["label"]),
                wh_per_1k_tokens=ProvenancedValue.from_reference(
                    float(r["value"]),
                    "Wh/1k output tokens",
                    str(r["cite"]),
                    confidence=r["confidence"],
                    low=float(r["low"]),
                    high=float(r["high"]),
                ),
                basis="output_tokens",
                note=str(r["note"]),
            )
            for r in _ROWS
        ],
        models=dict(_MODEL_CLASSES),
        default_class="frontier",
        note=(
            "LLM inference energy per 1,000 OUTPUT tokens, by model class, hand-curated from "
            f"published third-party measurements ({INFERENCE_ENERGY_VINTAGE}). No provider "
            "publishes a per-token energy figure for its hosted models, so these are "
            "`reference` estimates, never a metered fact about our own inference. Every row "
            "is banded because the published spread is roughly an order of magnitude, driven "
            "mostly by BOUNDARY: an accelerator-only figure excludes host CPU/DRAM, idle "
            "capacity and facility overhead, and Google's 2025-08 production measurement "
            "found the accelerator is only 58% of full-stack energy. The basis is OUTPUT "
            "tokens — decode dominates inference energy and prefill is far cheaper per token, "
            "so applying these to an input+output total would overstate a cache-heavy agentic "
            "workload several-fold. An unmapped model id is priced at `default_class` "
            "(frontier), never dropped."
        ),
    )


# --- committed reference artifact (data/reference/greenops/factors/inference-energy.yaml) ---

_RELPATH = Path("reference") / "greenops" / "factors" / "inference-energy.yaml"


def inference_energy_path(settings: Settings | None = None) -> Path:
    """Where the committed inference-energy table lives."""
    settings = settings or get_settings()
    return settings.data_dir / _RELPATH


def load_inference_energy(path: Path) -> InferenceEnergyTable:
    """Load a committed :class:`InferenceEnergyTable` YAML."""
    return InferenceEnergyTable.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
