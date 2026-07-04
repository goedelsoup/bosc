# AERMOD — engine provenance & binary sourcing

**Status:** live (deck generation + output parsing, #1178); the vendored binary and
AERMET/AERMAP met/terrain inputs (#1179) are an operator step, documented below.

The Tier-1 air-dispersion engine behind [`watermark.air.aermod`](../src/watermark/air/aermod/) —
the air sibling of the SWMM5 integration in [`watermark.hydrology.swmm`](../src/watermark/hydrology/swmm/).
`watermark.air.aermod.inp` builds an AERMOD control + source deck from the site's genset
stack parameters and permit-certified emission rates; `watermark.air.aermod.engine` runs the
EPA binary and parses the modeled ground-level concentrations. This note covers **where the
binary comes from and how it is pinned**, the explicit sub-task of #1178.

## Why this differs from SWMM

SWMM5 reaches us as a Python wheel (`pyswmm`, pinned in `pyproject.toml`) — `pip`/`uv`
resolves and installs the native engine. **AERMOD has no such package.** EPA distributes it
through [SCRAM](https://www.epa.gov/scram) as a Fortran **source** release plus reference
executables; running it is a build/vendor step, not a dependency install. So the engine is
**located on disk**, never imported:

- `Settings.aermod_bin` (`WATERMARK_AERMOD_BIN`) — an explicit path to the executable.
- else `aermod` on `PATH`.
- else nothing → `aermod_available()` is `False` and `run()` degrades to
  `AermodResult(available=False)`, exactly like `swmm_available()`. Deck generation and
  plotfile parsing stay fully testable **without** the binary (that's what CI exercises).

The binary is **not committed** to the repo (platform-specific, ~MB Fortran build, and the
corpus tree is evidence — not a place for third-party executables). It is an operator-
provided artifact, the way AERMET-processed met is.

## Obtaining and pinning the binary

1. Download the current AERMOD release from EPA SCRAM
   (<https://www.epa.gov/scram/air-quality-dispersion-modeling-preferred-and-recommended-models#aermod>).
   Record the **version stamp** (e.g. `23132` — AERMOD versions are `YYDDD` Julian dates)
   and the SCRAM download date; the version banner is echoed in every `aermod.out` and
   captured into `AermodResult.engine_version`.
2. Either use EPA's precompiled executable for your platform, or build from the published
   Fortran source with a Fortran compiler (`gfortran`), per EPA's `aermod_readme`. Pin the
   exact source zip you built from (filename + SCRAM date) alongside your deployment.
3. Point `WATERMARK_AERMOD_BIN` at the resulting `aermod` (or `aermod.exe`) and make it
   executable. Confirm with `watermark`'s engine probe (or a bare `aermod` run in a scratch
   dir with a valid `aermod.inp`).

Pin the **version stamp** in your run provenance so a concentration result is reproducible:
regulatory AERMOD is version-sensitive, and a re-run under a newer engine is a *different*
model, not a refresh of the old one.

## Met & terrain inputs (deferred — #1179)

A real AERMOD run also needs **AERMET-processed** surface (`.SFC`) and profile (`.PFL`) met
files, and (for elevated terrain) **AERMAP** receptor elevations. Those connectors are
#1179. Until then:

- The minimal acceptance run uses **flat terrain** (`MODELOPT ... FLAT`) and a **canned**
  met pair supplied by the operator; the deck's `ME` pathway just names the files.
- We do **not** commit a fabricated `.SFC`/`.PFL` — a met file we can't validate against a
  real engine would be an invented input, which the corpus discipline forbids. The
  end-to-end test skips until a validated canned pair (or the #1179 connector) exists.

## Provenance discipline (stack geometry)

The Lima permit (P0138965) **redacts engine make/model/size as CBI** (Comments 16/19,
Response 16), so it states **no** stack geometry. `assumed_stack_params()` therefore returns
`assumption`-tagged screening values for a large (~2.75 MW) stationary diesel genset — a
stated modeling input, never presented as the permit's. The **emission rate** *is* grounded
(permit-certified `lb/hr` → `g/s`, `derived`). A deck is thus honestly "assumed stack
geometry + certified emission rate"; a site that later obtains manufacturer stack data
supplies a `document`-tagged `GensetStackParams` instead (the #1180 seam).
