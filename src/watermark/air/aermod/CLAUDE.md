# CLAUDE.md — `watermark.air.aermod`

The **Tier-1 AERMOD dispersion** engine — the air sibling of
[`watermark.hydrology.swmm`](../../hydrology/swmm/). Gated behind the Tier-0 emissions
inventory (`watermark.air`). Defers to [`../CLAUDE.md`](../CLAUDE.md) and the root
[`CLAUDE.md`](../../../../CLAUDE.md).

- **Build a deck, run the binary, parse the output.** `inp.py` writes the AERMOD five-pathway
  control file (`CO`/`SO`/`RE`/`ME`/`OU`); `engine.py` locates + runs the EPA Fortran binary
  and parses its `PLOTFILE`s; `screening.py` wires the permit emission rates into a minimal
  single-source deck. `model.py` holds the typed, provenance-tagged deck inputs.
- **The binary is located on disk, never imported** — AERMOD is a SCRAM Fortran build, not a
  pip wheel (unlike `pyswmm`). Resolution: `WATERMARK_AERMOD_BIN` → `aermod` on `PATH` →
  nothing. Absent ⇒ `AermodResult(available=False)`, mirroring `swmm_available()`; deck
  generation + plotfile parsing stay testable without it (that's what CI runs). Provenance /
  version pinning: [`docs/AERMOD.md`](../../../../docs/AERMOD.md).
- **Stack geometry is an `assumption`, the emission rate is grounded.** The Lima permit
  redacts engine specs as CBI, so `assumed_stack_params()` returns `assumption`-tagged
  screening values — **never** presented as the permit's. The per-engine `lb/hr` is
  permit-certified and converts to `g/s` (`derived`). Don't fabricate stack dimensions as
  documented; a site with manufacturer data passes a `document`-tagged `GensetStackParams`
  (the #1180 seam).
- **Parse the `PLOTFILE`, not `aermod.out`.** The plotfile is a stable columnar format
  (`X Y CONC ZELEV ZHILL ZFLAG AVE GRP NUM_HRS NET_ID`); `parse_plotfile` reads X/Y/conc and
  skips `*`-comment lines. The human-oriented `aermod.out` is only mined for the version banner.
- **Met/terrain are #1179 (deferred).** The minimal run is **flat terrain + canned met**; the
  `ME` pathway just names the operator-supplied `.SFC`/`.PFL`. **Never commit a fabricated
  AERMET met file** — an unvalidatable invented input violates corpus discipline; the
  end-to-end test skips until a validated canned pair (or the #1179 connector) exists.
- **Site-agnostic.** Emission rate, fleet, and (future) stack data resolve from the active
  site's profile / permit extraction via `watermark.air.emissions` — never hardcoded to
  Lima/Bistrozzi.
