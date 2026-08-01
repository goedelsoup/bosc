"""The international AOI register — where the seeded sweep looks, and why (#1393, epic #1387).

The epic's locked driver is **follow the operators, capability first**: AOIs come from where
operators and interconnection actually are, *not* from where water is scarce. That decision is
load-bearing and easy to quietly reverse, so each AOI states its own ``selection_basis`` here and
the register republishes it verbatim beside the results. If a future AOI's basis reads like a
water argument, the driver has drifted.

An AOI is a **stated screening window**, not a boundary: the bbox is drawn generously enough to
catch a cluster's outlying campuses (Johor's reaches inland to the Sedenak/Kulai corridor, not
just Johor Bahru) and is not co-extensive with any administrative area. Nothing downstream treats
it as a jurisdiction.

The four here are the seeded track's starting set — two are the epic's own pilot nominees, and
the other two are the capability anchors that make those two legible. This is a register, not a
closed list: add an AOI by appending a profile with its basis stated.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# Every ISO 3166-1 alpha-2 code here is deliberately non-US. This is the *international* funnel;
# a US location belongs in the domestic records-first register, which has instruments this one
# structurally cannot get (see `watermark.facility.candidate`).
US = "US"


class Aoi(BaseModel):
    """One area of interest: a bbox, the country its PeeringDB slice is pulled from, and the
    stated reason it is being swept at all."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    label: str
    country: str  # ISO 3166-1 alpha-2 — also the PeeringDB `country` query
    # (south, west, north, east) in WGS84 — the Overpass bbox order.
    bbox: tuple[float, float, float, float]
    selection_basis: str

    @property
    def overpass_bbox(self) -> str:
        """The bbox as Overpass's ``(s,w,n,e)`` clause argument."""
        return ",".join(f"{v}" for v in self.bbox)

    def contains(self, lat: float, lon: float) -> bool:
        """Whether a point falls in this window (used to bbox-filter the country-wide PeeringDB
        slice down to the AOI)."""
        south, west, north, east = self.bbox
        return south <= lat <= north and west <= lon <= east


AOIS: dict[str, Aoi] = {
    aoi.slug: aoi
    for aoi in (
        Aoi(
            slug="singapore",
            label="Singapore",
            country="SG",
            bbox=(1.15, 103.6, 1.48, 104.1),
            selection_basis=(
                "The region's interconnection anchor — a small territory carrying one of the "
                "densest concentrations of carrier-neutral facilities in Asia Pacific, which is "
                "what 'capability first' means operationally. It is also the control for its own "
                "neighbour: Singapore is the constrained market Johor's buildout sits across the "
                "strait from, so sweeping one without the other would show the growth and hide "
                "the reason for it."
            ),
        ),
        Aoi(
            slug="johor",
            label="Johor (Iskandar / Sedenak corridor), Malaysia",
            country="MY",
            bbox=(1.25, 103.3, 1.95, 104.35),
            selection_basis=(
                "One of the epic's two nominated pilot AOIs: an operator-dense market with active "
                "buildout, adjacent to a constrained one. The window runs inland past Johor Bahru "
                "to the Kulai/Sedenak industrial corridor, where the newer campuses are, rather "
                "than stopping at the metro."
            ),
        ),
        Aoi(
            slug="queretaro",
            label="Querétaro, Mexico",
            country="MX",
            bbox=(20.35, -100.65, 20.95, -100.0),
            selection_basis=(
                "The epic's other nominated pilot AOI, and a deliberate contrast to the Asia "
                "Pacific pair: a newer inland cluster in a semi-arid basin, where the open-data "
                "coverage is thinner. Sweeping it tests whether the funnel degrades honestly "
                "where the priors are sparse instead of quietly reporting nothing."
            ),
        ),
        Aoi(
            slug="dublin",
            label="Dublin, Ireland",
            country="IE",
            bbox=(53.20, -6.60, 53.55, -6.05),
            selection_basis=(
                "A mature European cluster whose growth is bounded by grid connection capacity "
                "rather than land — the closest international analog to the power-constrained "
                "posture the domestic sites are read against, and a second capability anchor "
                "outside Asia Pacific so the seeded register is not a one-region sample."
            ),
        ),
    )
}


def get_aoi(slug: str) -> Aoi:
    """One AOI by slug (``KeyError`` if unregistered — the caller names a real window or fails)."""
    return AOIS[slug]
