# Regulatory enforcement & framework instruments (original records)

**Collection:** `regulatory/` · immutable source evidence

Enforcement / regulatory instruments a watershed point must be read against — the
**enforcement** history of the systems that carry its wastewater, and the standing
**regulatory framework** permits that govern its site. Distinct from
[`watershed/`](../watershed/README.md) (conservation *context*, not enforcement
action) and from the site-specific permit records under
[`permits/`](../permits/README.md) and [`oepa/`](../oepa/README.md). Raw bytes are
never edited.

The flat files below are Lima's (Allen County). A **peer site's** enforcement
instruments nest one level down in a `<slug>/` subdirectory — that segment *is* the
site attribution the corpus scope derives (`*/<slug>`, #1405), so a West Union order
reaches West Union and never renders inside Lima's record. Its extraction must keep
the same segment (`data/extracted/regulatory/<slug>/`).

## Contents

| File | What |
|---|---|
| `allen-co-cwa-consent-decree-1996.pdf` | The 1996 Clean Water Act consent decree for Allen County. |
| `allen-co-sanitary-cna-2005.pdf` | 2005 Allen County sanitary capacity/needs analysis (CNA). |
| `OHC000006.pdf` | Ohio EPA **statewide** NPDES Construction Stormwater General Permit (eff. 2023-04-23 → 2028-04-22) — the framework the BOSC site's still-owed CGP coverage is issued under. **Not** a site coverage record. |
| `OHC000006_RTC.pdf` | Division of Surface Water Response to Comments for OHC000006 (public hearing 2023-01-23). |

### Per-site (`<slug>/`)

| Path | What |
|---|---|
| `west-union/Village-of-West-Union-Consent-Order-1993.pdf` | *State of Ohio ex rel. Fisher v. Village of West Union* — Adams County C.P. 89-CIV-228, entered 1993-06-29. R.C. Ch. 6111 consent order on NPDES `0PC00019*CD`: interim effluent limits (Appendix "A"), a $5,000 penalty, elimination of all sanitary-sewer overflows and bypasses, and a plant-improvement schedule to 1995-05-01. Published by the Ohio AG's Environmental Enforcement Section; provenance + verified hash in `west-union/filename-map.yaml`. |

Treat each as of its own stated date; verify any quoted obligation against the
source page before citing in a filing.
