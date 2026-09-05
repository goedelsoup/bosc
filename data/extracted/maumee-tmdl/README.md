# maumee-tmdl — extracted

Reviewed extractions from the **Maumee Watershed Nutrient TMDL** and its supporting record, whose
source PDFs are in [`data/documents/maumee-tmdl/`](../../documents/maumee-tmdl/).

The TMDL is a basin instrument, not a site one: it assigns a total-phosphorus wasteload allocation
to every significant discharger in the Ohio Maumee watershed, so the same appendix is read once per
site for that site's rows. Findlay's rows were extracted first, under
[`data/extracted/findlay/tmdl/`](../findlay/tmdl/) — a peer site keeps its artifacts in its own
slug-scoped subtree. This collection holds the reads made from the reference build's scope.

| file | subject |
|---|---|
| [`maumee-tp-wla-lima-loop.epa.yaml`](maumee-tp-wla-lima-loop.epa.yaml) | The eight Allen County allocations — Lima WWTP `2PE00000`, Shawnee II, Lima Refining, American-Bath, American II, Elida, Cridersville, Bluffton — from Appendix 4 and the general permit `OHP000001` that makes them enforceable; plus the ten Lima-loop allocations from the **near-field** Ottawa River (Lima Area) TMDL, via Appendix 5 |

## Reading these safely

Three things about the source tables have already caused, or would have caused, a wrong figure:

- **Tables A4.1 and A4.5 disagree on several allocations, and A4.1 is the operative one.** A4.5's
  second column is headed `WLA` but restates Shawnee II as 0.51 MT against A4.1's 0.75, and Elida
  as 0.21 against 0.34. `OHP000001` Part IV.A.1 settles it in A4.1's favour (750 kg, 340 kg). Cite
  A4.1 or the permit for a limit; cite A4.5 only for the reported loads beside it.
- **Table A4.5's first numeric column is a 2008 baseline, not a reported year.** The seven columns
  are `2008 / WLA / 2017 / 2018 / 2019 / 2020 / 2021`.
- **The CSO allocation (Table A4.3) is additional to the Table A4.1 allocation for the same
  permit.** Lima WWTP carries both, and A4.1 says so in its own preamble.

These are digitally generated PDFs, so the embedded text layer carries the right digits — but a
table's text layer does not reliably carry the *column* a digit sits in, and this appendix prints
two facilities with genuinely identical values. Every figure in the extractions here was re-read
from a 200 DPI render of its page before being written down.

## Two TMDLs, not one

The far-field **Maumee Watershed Nutrient TMDL** (2023) is about Lake Erie's western-basin algal
blooms and allocates a **spring-season** load. A separate **Ottawa River Watershed (Lima Area)
TMDL** (approved 2014-04-15) is about in-stream aquatic life use in Lima's own river and allocates
a **daily** load. Both reach every Lima-loop facility, and neither document says the other is
superseded.

Their numbers are not directly comparable. Appendix 4's "Daily*" column is the spring load divided
by 153 days — the footnote says in terms that "The total maximum daily load is not equivalent to a
maximum daily limit" — while the near-field figures are the near-field TMDL's own allocations.

⚠️ **The Ottawa River (Lima Area) TMDL Report is not in this corpus.** What is here is Appendix 5's
one-paragraph summary and its allocation table. Ohio EPA publishes the report at
`epa.ohio.gov/static/Portals/35/tmdl/OttawaLima_Report_Final.pdf`. It is a named, cheap gap.
