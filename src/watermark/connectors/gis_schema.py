"""Declarative field-maps for the jurisdiction-agnostic GIS connectors (#237).

The County/City parcel / zoning / floodzone connectors
(:mod:`watermark.hydrology.connectors.allen_gis`, :mod:`watermark.hydrology.connectors.lima_gis`)
used to hardcode one jurisdiction's ArcGIS **field names** and **value encodings**. This
module lifts those into per-site *schema* objects, so adding a new jurisdiction is config —
a :class:`GisParcelSchema` / :class:`GisZoningSchema` / :class:`GisFloodSchema` registered
on its :class:`watermark.sites.SiteProfile` — rather than a copied connector. It mirrors the OPC
``Profile`` idiom (:mod:`watermark.profiles`): the data carries the field names; the connector
code is jurisdiction-agnostic.

These are pure pydantic models (only ``pydantic`` plus the dependency-free
:mod:`watermark.provenance` core imported), and they live under the
**neutral** :mod:`watermark.connectors` package — *not* ``watermark.hydrology.connectors`` — so
:mod:`watermark.sites` can carry the schema *constants* without an import cycle (the chain
``config → sites → here`` stays acyclic; ``watermark.hydrology.connectors`` would pull in
``_cache → config`` and close a loop). The schema *instances* (Lima/Findlay/NFHL) live with
the profiles in :mod:`watermark.sites`, where site-specific values belong.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.provenance import EvidenceRegister

_IdNormalize = Literal["dashless", "verbatim"]
_HttpMethod = Literal["GET", "POST"]


class GisMeta(BaseModel):
    """The provenance block a connector reproduces verbatim into its ``write_*`` YAML meta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    source: str
    source_url: str
    caveats: tuple[str, ...]


class GisDefenseMeta(BaseModel):
    """Provenance prose for the (jurisdiction-specific) defense-industry land scan.

    ``army_controlled_note`` is the reader-facing paragraph; ``enclave_attribution`` +
    ``enclave_attribution_tag`` are the same claim as *data* (#1663, ME-D) — what the
    federally-held cluster is identified as, and the register of that identification. The pair is
    stamped onto every ``ScanParcel`` the enclave filter returns, so a consumer keys on a typed
    field instead of parsing the note's ``[inference]`` prefix. It is per-jurisdiction and required
    rather than defaulted: a site whose enclave identity comes from a base-boundary record, not an
    owner+tax-district read, states ``verified`` and must say so deliberately.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    source: str
    source_url: str
    scan: str
    finding: str
    army_controlled_note: str
    enclave_attribution: str  # what the federally-held cluster is identified AS
    enclave_attribution_tag: EvidenceRegister  # and the register of that identification
    caveats: tuple[str, ...]


class GisDefenseConfig(BaseModel):
    """A jurisdiction's defense-owner-scan + federal-enclave configuration.

    Present only where there is a federally-held enclave to surface (Lima = the JSMC / Lima
    Army Tank Plant). A site without one leaves ``GisParcelSchema.defense = None`` and the
    defense-scan entrypoints refuse rather than run Lima's owner/tax-district filter elsewhere.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # The owner fields OR-ed in the defense pattern query, in their exact clause order — this
    # order is part of the request ``where`` string and therefore the connector cache key.
    owner_scan_fields: tuple[str, ...]
    enclave_owner: str  # the federally-held cluster's owner name (e.g. "UNITED STATES")
    enclave_tax_district: str  # and its tax district (e.g. "L35")
    meta: GisDefenseMeta


class GisParcelSchema(BaseModel):
    """One jurisdiction's parcel/CAMA ArcGIS layer: field names + value encodings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector: str  # cache/fixtures subfolder + log name (Lima = "allen_gis")
    reference_dir: str  # committed reference subfolder under data/reference (Lima = "allen-gis")
    page_size: int  # the layer's maxRecordCount
    out_fields: tuple[str, ...]  # the full ordered outFields list (drives the request string)
    # field names for each typed ``Parcel`` attribute (selected by name, never by index):
    id_field: str
    owner_field: str
    owner_2_field: str
    deeded_owner_field: str
    situs_fields: tuple[str, ...]  # joined into the situs address
    owner_addr_fields: tuple[str, ...]  # joined into the owner mailing address
    land_use_field: str
    acres_field: str
    market_land_field: str
    market_improvement_field: str
    market_total_field: str
    cauv_field: str
    tax_district_field: str
    school_field: str
    neighborhood_field: str
    sale_date_field: str
    sale_amount_field: str
    valid_sale_field: str
    # value encodings:
    id_normalize: _IdNormalize  # how a deed id is normalized to the layer's stored id
    # the sale-date field's encoding: an ``M(M)DDYYYY`` integer ("mmddyyyy", Lima), an already-ISO
    # string ("iso"), a ``MM-DD-YY`` two-digit-year string ("mmddyy", Putnam - pivoted by the
    # standard C/strptime ``%y`` convention 69-99 -> 1900s / 00-68 -> 2000s), an ``M/D/YYYY``
    # four-digit-year string with an optional trailing clock time ("mdyyyy_slash", Clinton - the
    # county serves its CAMA conveyance date pre-formatted as text, e.g.
    # "12/10/2025 12:00:00 AM", NOT as an esriFieldTypeDate), an Esri epoch-milliseconds integer
    # ("epoch_millis", an esriFieldTypeDate - e.g. Allen County, IN), or dropped ("none").
    date_decode: Literal["mmddyyyy", "iso", "mmddyy", "mdyyyy_slash", "epoch_millis", "none"]
    # the land-use field's encoding: a bare numeric code ("int", the default — Lima's LANDUSE) or a
    # "<code>: <label>" string whose leading integer is the code ("leading_int" — Ohio's StateLUC).
    land_use_decode: Literal["int", "leading_int"] = "int"
    # an optional ``where`` fragment ANDed into every parcel query — for a multi-jurisdiction layer
    # that must be scoped (e.g. the Ohio statewide layer filtered to one county: ``County='Hancock'``).
    # Empty (the default) leaves the query string byte-identical, so single-jurisdiction layers are
    # unaffected (and the connector cache key is unchanged).
    query_scope: str = ""
    deed_id_regex: str  # the deed-style parcel-id pattern scanned from the corpus
    meta: GisMeta
    defense: GisDefenseConfig | None = None


class GisCitedZoningMeta(BaseModel):
    """Provenance + the in/out-of-jurisdiction finding fragments for the cited-zoning scan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    source: str
    finding_lead: str  # "fall within the City of Lima zoning jurisdiction"
    in_city_finding: str  # appended when there ARE in-jurisdiction parcels (e.g. ".")
    out_of_city_finding: str  # the explanatory clause when none are in-jurisdiction
    caveats: tuple[str, ...]


class GisZoningSchema(BaseModel):
    """One jurisdiction's zoning ArcGIS layer: field names + provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector: str  # Lima = "lima_gis"
    reference_dir: str  # committed reference subfolder (Lima = "lima-gis")
    page_size: int
    object_id_field: str
    # ``None`` for a polygon-only zoning layer with no parcel-id field (e.g. Findlay): the
    # district catalog still works; the parcel-join entrypoints refuse cleanly.
    parcel_field: str | None
    zoning_field: str
    http_method: _HttpMethod
    id_normalize: _IdNormalize
    meta: GisMeta  # write_zoning_districts provenance
    cited_meta: GisCitedZoningMeta | None = None  # write_cited_zoning (needs a parcel join)

    @property
    def out_fields(self) -> tuple[str, ...]:
        """The zoning-query outFields, in the layer's request order (parcel field if present)."""
        fields = (self.object_id_field, self.parcel_field, self.zoning_field)
        return tuple(f for f in fields if f)


class GisFloodSchema(BaseModel):
    """One jurisdiction's (or the national FEMA NFHL) flood-hazard ArcGIS layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector: str  # Lima = "lima_gis_flood"
    reference_dir: str  # committed reference subfolder for the catalog (Lima = "lima-gis")
    page_size: int
    object_id_field: str
    fld_zone_field: str
    zone_subtype_field: str
    sfha_field: str
    static_bfe_field: str
    dfirm_id_field: str
    source_cit_field: str
    http_method: _HttpMethod
    bfe_sentinel: float  # the "no static BFE" sentinel (never a real elevation)
    sfha_true_value: str  # the value of the SFHA flag that means True (e.g. "T")
    meta: GisMeta

    @property
    def out_fields(self) -> tuple[str, ...]:
        """The floodzone-query outFields, in the layer's request order."""
        return (
            self.object_id_field,
            self.fld_zone_field,
            self.zone_subtype_field,
            self.sfha_field,
            self.static_bfe_field,
            self.dfirm_id_field,
            self.source_cit_field,
        )
