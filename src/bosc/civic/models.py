"""Pydantic models for the civic-records subsystem.

The registry (``Subdivision`` + ``Registry``) is the committed, hand-reviewed
artifact under ``data/reference/subdivisions/``; ``DiscoveryResult`` and
``MeetingDoc`` are produced by the connectors. Grounded roster facts and
live-discovered publishing facts are kept in separate fields so the two confidence
levels never blur (see the reference README).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Platform(StrEnum):
    """How a body publishes its minutes/agendas online.

    Values are stable identifiers a per-platform fetcher dispatches on. ``unknown``
    means "not yet discovered" — never "publishes nothing".
    """

    CIVICPLUS = "civicplus"  # CivicPlus / CivicEngage "Agenda Center"
    GRANICUS = "granicus"  # Granicus / Legistar / GovAccess
    BOARDDOCS = "boarddocs"  # Diligent BoardDocs
    CIVICCLERK = "civicclerk"  # CivicClerk meeting portal
    REVIZE = "revize"  # Revize municipal CMS
    WORDPRESS = "wordpress"  # WordPress site (typically PDF links on a page)
    WIX = "wix"  # Wix site builder
    SQUARESPACE = "squarespace"  # Squarespace site builder
    GOVOFFICE = "govoffice"  # GovOffice / govoffice.com
    FACEBOOK = "facebook"  # posts to a Facebook page only
    REQUEST_ONLY = "request_only"  # no online posting found; records-request only
    UNKNOWN = "unknown"  # not yet discovered


class Discovered(BaseModel):
    """Provenance for a live-web publishing finding."""

    model_config = ConfigDict(extra="forbid")

    asof: str  # ISO date the finding was made (yyyy-mm-dd)
    method: str  # how it was verified (e.g. "web")
    note: str | None = None


class Publishing(BaseModel):
    """Where a body publishes its minutes/agendas (the discovered block)."""

    model_config = ConfigDict(extra="forbid")

    website: str | None = None
    records_url: str | None = None
    platform: Platform = Platform.UNKNOWN
    discovered: Discovered | None = None


class Subdivision(BaseModel):
    """One Allen County meeting-holding body.

    Grounded fields (``name``..``office``) are verbatim from a committed county
    roster named by ``grounded_from``; ``publishing`` is filled by discovery.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    type: str  # township | city | village | special_district | county_department
    governing_body: str | None = None
    meeting_schedule: str | None = None  # verbatim standing cadence
    office: str | None = None
    grounded_from: str | None = None  # id of the roster the grounded facts came from
    note: str | None = None
    publishing: Publishing = Publishing()


class Registry(BaseModel):
    """The whole subdivisions registry: ``meta`` provenance + the bodies."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, object]
    subdivisions: list[Subdivision]

    def get(self, slug: str) -> Subdivision | None:
        """Return the body with this slug, or ``None``."""
        return next((s for s in self.subdivisions if s.slug == slug), None)

    def with_website(self) -> list[Subdivision]:
        """Bodies that have a homepage on record (discovery can run against them)."""
        return [s for s in self.subdivisions if s.publishing.website]

    def undiscovered(self) -> list[Subdivision]:
        """Bodies never run through discovery (no ``discovered`` provenance yet).

        Distinct from ``platform: unknown``: a body can be *looked at* (has a
        ``discovered`` block + a website) yet have an unfingerprinted CMS.
        """
        return [s for s in self.subdivisions if s.publishing.discovered is None]


class DiscoveryResult(BaseModel):
    """The outcome of probing one body's website (read-only; not auto-committed)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    homepage: str | None  # URL actually fetched (after redirects), or None if not fetched
    platform: Platform
    records_url: str | None  # best minutes/agendas page found
    records_url_candidates: list[str]  # all minutes/agenda/meeting links found
    signals: list[str]  # platform signatures that matched
    note: str | None = None


class MeetingDoc(BaseModel):
    """One minutes or agenda document a fetcher located for a body.

    Values are passed through verbatim from the source listing; ``None`` means the
    listing carried no value (never a fabricated default).
    """

    model_config = ConfigDict(extra="forbid")

    slug: str  # owning subdivision
    body: str | None  # the specific board (e.g. "City Council", "Planning Commission")
    kind: str  # "minutes" | "agenda" | "packet" | "other"
    title: str | None
    date: str | None  # ISO yyyy-mm-dd if parseable from the listing, else None
    url: str  # source document URL (verbatim)
