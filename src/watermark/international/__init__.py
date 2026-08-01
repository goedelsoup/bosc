"""The international data-center candidates funnel (epic #1387).

Imagery-and-open-data-led *identification* abroad, as against the domestic records-first sweep.
See :mod:`watermark.international.model` for the artifact class and the evidentiary rules it
enforces at the type level, :mod:`watermark.international.aois` for where the sweep looks and
why, and :mod:`watermark.international.register` for the assembly.
"""

from __future__ import annotations

from watermark.international.aois import AOIS, Aoi, get_aoi
from watermark.international.model import (
    CORROBORATION_RADIUS_M,
    AoiResult,
    Candidate,
    CandidatesRegister,
    CandidateTag,
    CompetingClaim,
    CoolingType,
    Corroboration,
    DetectionBasis,
    OperatorAttribution,
    PriorObservation,
    PriorSource,
    SourceTerms,
    build_candidate,
    haversine_m,
)
from watermark.international.register import (
    DEFAULT_SCOPE,
    REGISTER_DIR,
    SOURCE_TERMS,
    build_register,
    cluster_observations,
    load_register,
    register_path,
    render_register,
    save_register,
    sweep_aoi,
)

__all__ = [
    "AOIS",
    "CORROBORATION_RADIUS_M",
    "DEFAULT_SCOPE",
    "REGISTER_DIR",
    "SOURCE_TERMS",
    "Aoi",
    "AoiResult",
    "Candidate",
    "CandidateTag",
    "CandidatesRegister",
    "CompetingClaim",
    "CoolingType",
    "Corroboration",
    "DetectionBasis",
    "OperatorAttribution",
    "PriorObservation",
    "PriorSource",
    "SourceTerms",
    "build_candidate",
    "build_register",
    "cluster_observations",
    "get_aoi",
    "haversine_m",
    "load_register",
    "register_path",
    "render_register",
    "save_register",
    "sweep_aoi",
]
