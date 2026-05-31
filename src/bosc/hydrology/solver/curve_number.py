"""SCS Curve Number runoff method (USDA TR-55).

Excess (direct) rainfall from a storm depth and a curve number:

    S  = 1000/CN - 10          maximum retention (in)
    Ia = 0.2 * S               initial abstraction (in)
    Q  = (P - Ia)^2 / (P - Ia + S)   for P > Ia, else 0

Curve numbers come from :func:`cn_for` (NLCD class x hydrologic soil group, from the
cited ``cn-lookup.yaml``); composite CN over a mixed area is area-weighted.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from bosc.config import Settings, get_settings

_HSG = ("A", "B", "C", "D")


@lru_cache(maxsize=4)
def _load_table(data_dir: str) -> dict[str, Any]:
    from pathlib import Path

    path = Path(data_dir) / "reference" / "hydrology" / "cn-lookup.yaml"
    if not path.is_file():
        return {}
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def _resolve_class(table: dict[str, Any], land_cover: int | str) -> int:
    """Map an NLCD code or an alias name to an NLCD class code."""
    if isinstance(land_cover, int):
        return land_cover
    aliases = table.get("aliases", {})
    if land_cover in aliases:
        return int(aliases[land_cover])
    raise KeyError(f"unknown land cover {land_cover!r}")


def cn_for(
    land_cover: int | str,
    hsg: str,
    *,
    settings: Settings | None = None,
) -> float:
    """Curve number (AMC-II) for one land cover on one hydrologic soil group."""
    settings = settings or get_settings()
    table = _load_table(str(settings.data_dir))
    code = _resolve_class(table, land_cover)
    classes = table.get("classes", {})
    row = classes.get(code) or classes.get(str(code))
    group = hsg.strip().upper()[:1]
    if row is None or group not in _HSG:
        raise KeyError(f"no CN for class {code} / HSG {hsg!r}")
    return float(row[group])


def composite_cn(parts: list[tuple[float, float]]) -> float:
    """Area-weighted curve number from ``(area, cn)`` pairs. Falls back to 70."""
    total = sum(a for a, _ in parts)
    if total <= 0:
        return 70.0
    return sum(a * cn for a, cn in parts) / total


def adjust_amc(cn_ii: float, amc: str) -> float:
    """Adjust an AMC-II curve number to dry (I) or wet (III) conditions."""
    if amc == "I":
        return 4.2 * cn_ii / (10.0 - 0.058 * cn_ii)
    if amc == "III":
        return 23.0 * cn_ii / (10.0 + 0.13 * cn_ii)
    return cn_ii


def storage_s(cn: float) -> float:
    """Maximum potential retention S (in) for a curve number."""
    if cn <= 0:
        raise ValueError("curve number must be positive")
    return 1000.0 / cn - 10.0


def excess_rainfall(
    cumulative_p: NDArray[np.float64],
    cn: float,
) -> NDArray[np.float64]:
    """Cumulative excess (direct) rainfall (in) from cumulative gross rainfall.

    Apply the CN equation to the *cumulative* depth at each step, so the result is
    a monotonic cumulative-excess series; differencing it gives the incremental
    runoff that feeds the unit hydrograph.
    """
    s = storage_s(cn)
    ia = 0.2 * s
    eff = cumulative_p - ia
    q = np.where(eff > 0.0, eff**2 / (eff + s), 0.0)
    return np.asarray(q, dtype=np.float64)
