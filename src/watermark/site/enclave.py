"""Export the committed federal-enclave profile as a typed feed (#1664, epic #1659 ME-E).

Publishes ``data/reference/<slug>/enclave.yaml`` (assembled by ``watermark enclave`` from the
enclave's grounding record + the DoD MIRTA / EPA SDWIS / EPA ECHO / EPA RSEI registers). The
enclave peer of :mod:`watermark.site.rsei`: the artifact is already a clean, provenance-carrying
Pydantic model, so the feed **is** the model — nothing is re-keyed across the seam.

Enclave-gated: ``None`` (feed skipped) for every site with no ``federal_installation`` facility,
which is every site but WPAFB today.
"""

from __future__ import annotations

from watermark.config import Settings, get_settings
from watermark.enclave import EnclaveProfile, load_enclave


def export_enclave(settings: Settings | None = None) -> EnclaveProfile | None:
    """The active site's committed enclave profile as a feed, or ``None`` when it has none."""
    settings = settings or get_settings()
    return load_enclave(settings)
