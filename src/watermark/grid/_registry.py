"""The one serving-utility registry, keyed by EIA-861 utility number (#1645/H2).

The FERC Form-1 identity (:mod:`watermark.grid.ferc`) and the parent/PJM-zone provenance
(:mod:`watermark.grid.utility`) used to be two dicts — ``_FORM1_FILER`` and ``_UTILITY_GRID`` —
keyed by the same number and describing the same utilities. A key added to one and not the
other is silent: that is exactly how WPAFB/Xenia (#4922, AES Ohio) lost their FERC filer and
fell back to "the serving utility" (A5/#1638). #1638 could only bolt a keyset-equality test
across the two; collapsing them here makes the drift **unrepresentable**, and retires that test.

Utilities are added when a registered site's ``SiteProfile.eia861_utility_number`` names one.
An unlisted number is not an error — :func:`utility_identity` degrades to a neutral identity
built from the EIA-861 name, asserting no FERC filer and no RTO (B2/#1639: PJM is never
assumed, since much of Indiana and any future MISO/SPP site is not PJM).
"""

from __future__ import annotations

from typing import NamedTuple

__all__ = ["SERVING_UTILITIES", "UtilityIdentity", "is_registered", "utility_identity"]


class UtilityIdentity(NamedTuple):
    """A serving utility's FERC identity + its parent / PJM transmission-zone provenance."""

    # --- FERC Form-1 identity (grid/ferc.py) ---
    short: str  # short label woven into the seam prose, e.g. "AEP Ohio"
    operating_company: str  # FERC Form-1 filer (IOU operating company), e.g. "Ohio Power Company"
    files_form1: bool  # IOUs file FERC Form 1; municipal / cooperative systems do not
    # --- Parent + market provenance (grid/utility.py) ---
    holding_company: str
    holding_citation: str
    ba_citation: str
    rto_citation: str


# Lima/Findlay/Van Wert = Ohio Power (#14006); Fort Wayne = Indiana Michigan Power (#9324);
# Toledo = Toledo Edison (#18997, the first non-AEP utility — PJM's ATSI zone); the Miami-basin
# sites (WPAFB/Xenia/Troy-Piqua/Sidney/Greenville/Wilmington) = Dayton P&L / AES Ohio (#4922,
# PJM's DAY zone); Bryan = a municipal system (#2439) — an AMP member, not a FERC Form-1 filer.
SERVING_UTILITIES: dict[int, UtilityIdentity] = {
    14006: UtilityIdentity(
        short="AEP Ohio",
        operating_company="Ohio Power Company",
        files_form1=True,
        holding_company="American Electric Power (AEP)",
        holding_citation="AEP Ohio is the Ohio operating company of American Electric Power",
        ba_citation="AEP's Ohio (AEP/APS) transmission zone is within the PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for AEP Ohio",
    ),
    9324: UtilityIdentity(
        short="AEP I&M",
        operating_company="Indiana Michigan Power Company",
        files_form1=True,
        holding_company="American Electric Power (AEP)",
        holding_citation="Indiana Michigan Power (I&M) is an AEP operating company",
        ba_citation="Indiana Michigan Power's transmission zone is within the PJM RTO footprint",
        rto_citation=(
            "PJM is the FERC-jurisdictional wholesale-market RTO for Indiana Michigan Power"
        ),
    ),
    18997: UtilityIdentity(
        short="FirstEnergy (Toledo Edison)",
        operating_company="The Toledo Edison Company",
        files_form1=True,
        holding_company="FirstEnergy Corp",
        holding_citation="Toledo Edison is an Ohio operating company of FirstEnergy Corp",
        ba_citation=(
            "Toledo Edison's ATSI (FirstEnergy) transmission zone is within the PJM RTO footprint"
        ),
        rto_citation=(
            "PJM is the FERC-jurisdictional wholesale-market RTO for Toledo Edison (ATSI zone)"
        ),
    ),
    2439: UtilityIdentity(
        # The network's first MUNICIPAL utility (Bryan, OH) — no IOU holding company; its
        # wholesale power + PJM scheduling are through American Municipal Power (AMP).
        short="Bryan Municipal Utilities",
        operating_company="Bryan Municipal Utilities",
        files_form1=False,
        holding_company="City of Bryan (municipal; American Municipal Power member)",
        holding_citation="Bryan Municipal Utilities is a municipally-owned electric system "
        "with no IOU holding company; its wholesale power and PJM scheduling are through "
        "American Municipal Power (AMP), the Ohio municipal joint-action agency",
        ba_citation="Bryan's municipal load is scheduled into the PJM RTO footprint via "
        "American Municipal Power (EIA-861S BA Code PJM)",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Bryan (AMP/PJM)",
    ),
    4922: UtilityIdentity(
        # The Miami-basin serving IOU (WPAFB #442, Xenia #444) — Dayton Power & Light,
        # d/b/a AES Ohio, the AES Corporation operating company; its transmission zone is
        # PJM's **DAY** zone, the network's first non-AEP/non-ATSI IOU zone.
        short="AES Ohio (Dayton P&L)",
        operating_company="The Dayton Power and Light Company",
        files_form1=True,
        holding_company="The AES Corporation (AES Ohio)",
        holding_citation="Dayton Power & Light Co does business as AES Ohio, the Ohio "
        "operating company of The AES Corporation",
        ba_citation="Dayton Power & Light's (AES Ohio) DAY transmission zone is within the "
        "PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Dayton Power "
        "& Light (AES Ohio)",
    ),
}


def is_registered(utility_number: int) -> bool:
    """Whether this EIA-861 utility is one the registry confirms (vs. an unlisted fallback).

    The confirmed set is what lets :mod:`watermark.grid.utility` report PJM as a **fact** — the
    entry encodes the transmission zone. An unlisted utility's BA stays unconfirmed (B2/#1639).
    """
    return utility_number in SERVING_UTILITIES


def utility_identity(utility_number: int, utility_name: str = "") -> UtilityIdentity:
    """The registered identity for a utility, else a neutral one built from its EIA-861 name.

    ``utility_name`` is the EIA-861 name, used only to phrase the unlisted fallback; the FERC
    seam resolves an identity from the profile alone and passes nothing. The fallback names no
    holding company beyond the utility itself and **claims no RTO** — an unlisted utility's
    balancing authority is resolved separately (profile pin → confirmed map → unconfirmed).
    """
    known = SERVING_UTILITIES.get(utility_number)
    if known is not None:
        return known
    name = utility_name or "the serving utility"
    return UtilityIdentity(
        short="the serving utility",
        operating_company="the serving utility",
        files_form1=True,
        holding_company=name,
        holding_citation=f"{name} parent/holding company — identified from the EIA-861 record",
        ba_citation=(
            f"{name}'s balancing authority / RTO is not confirmed (see SiteProfile.ba_code)"
        ),
        rto_citation=f"{name}'s wholesale-market RTO is not confirmed (see SiteProfile.ba_code)",
    )
