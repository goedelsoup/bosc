# docs/

Curated narrative / analysis layer for Project BOSC — the prose that frames and
synthesizes the structured data under [`data/`](../data/). The site generator
(`watermark.site`) mirrors this tree into the published site alongside the extracted
artifacts.

## Top-level notes

| File | What | Generated? |
|---|---|---|
| `COURSE.md` | Research course — what we're investigating and what to build next. | hand-written (living draft) |
| `DOSSIER.md` | Cross-document synthesis of everything deconstructed from the corpus. | hand-written |
| `HYDROLOGY.md` | Tier-0 municipal water-flow findings. | **`watermark`-generated** (`watermark.hydrology`); figures tagged `[verified]`/`[assumption]` |
| `COMPUTE.md` | The facility's compute / AI capacity, derived from disclosed power/water/footprint by three bracketing methods. | **hand-written** — figures derived by `watermark compute` (`watermark.facility`), which prints to console; the doc is authored from that output (no compute-doc writer yet). Figures tagged `[verified]`/`[reference]`/`[inference]` |
| `ECONOMICS.md` | Demand-side companion to HYDROLOGY — regional cloud-consumer demand & public benefits. | hand-assembled over cited sources |
| `AERMOD.md` | Tier-1 air-dispersion engine (`watermark.air.aermod`): binary provenance/pinning + the assumed-stack-geometry caveat. | hand-written (technical note, `**Status:**`-headed) |
| `onboarding.md` | Runbook for bringing a new watershed-point site online (`watermark onboard <slug>` → review gate → manual promotion). | hand-written |

## Subdirs

- [`legal/`](legal/) — legal analysis memos (mandamus, proponent case).
- [`reference/periplus/`](reference/periplus/) — notes carried over from the Periplus fork.

## Conventions

Note per-file whether content is **`watermark`-generated** or **hand-written** —
generated docs should not be hand-edited (regenerate the source instead), and
hand-written analysis must cite the underlying corpus/source for every factual claim.
Never invent a figure or a source. **"Generated" means a `watermark` command *writes
the file*** (e.g. `watermark hydro-report --write` → `HYDROLOGY.md`); a command that
only *prints* a derivation (e.g. `watermark compute`) does **not** make its doc generated.

### `**Status:**` header

Point-in-time docs (design notes, spikes, decision records) carry a **`**Status:**`**
line as the first paragraph under the H1, so status is greppable and can't silently go
stale (`grep -rl '^\*\*Status:\*\*' docs/`). Vocabulary:

- **`live`** — describes a shipped, current system.
- **`design`** — a plan for something not yet built (name the epic; e.g. `docs/auth.md`).
- **`adopted`** — a design that has since been built (point to the steady-state home).
- **`superseded`** — a decision record whose outcome was later reversed.
- **`hand-written` / `generated`** — the axis above, for derivation docs.

Add an `(as of <YYYY-MM-DD>)` date where the status could drift.
