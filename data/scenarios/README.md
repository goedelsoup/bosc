# Water-balance scenarios

Named what-if inputs for the hydrology water-balance model (`watermark.hydrology.scenario`).
Each scenario is a committed YAML of tagged inputs (value, unit, `source`, `citation`,
`confidence`, `asof`) that the model runs over.

## Files

| File | What |
|---|---|
| `baseline.scenario.yaml` | Current municipal loop, **no** data-center cooling draw (cooling demand 0.0 MGD). The reference case. |
| `buildout.scenario.yaml` | The corridor build-out case with campus cooling load. |

## Per-site scenarios (`<slug>/`)

Lima (the reference layout) keeps the flat files above; **every other site writes under its own
slug** — `scenarios_dir()` in `watermark.hydrology.scenario` is the single definition both the
writer and the exporter's reader use. It exists because they used to compute the location
independently and disagree (#1995): `watermark --site <peer> scenario --write` wrote the flat
path, overwriting Lima's committed `buildout.scenario.yaml`, while the peer that ran it still
exported an empty `hydrology-scenarios` feed.

| Dir | What |
|---|---|
| `sidney/` | The AWS "Project Galaxy" campus, driven by the **contracted** water account rather than by an IT-load screen (#1995) — see below. |

**Sidney is the network's inverse case**, and it is why the buildout intake has a document rung
at all. Everywhere else a campus discloses a load and hides its water; there AWS has disclosed no
MW and no floor area, but the City's executed Res. 26-26 service agreement states the gallons —
so `cooling_demand` carries `source: document` and cites the instrument, instead of being derived
from the investment-scaled IT-load bracket. The derived archetype basis still rides along on
`scenario.basis` as the cross-check, and it is worth reading beside the headline: the contracted
0.0126 MGD sits far below that basis's 0–4.03 MGD undisclosed-method bracket.

⚠️ **Regenerate with a cold NWIS cache.** `watermark --site <slug> scenario --offline --write` is
the command, and on a clean checkout it writes `receiving_live: null` — the committed convention
(Lima's does too). On a machine with a warm `data/cache/hydrology/nwis/` the same command fills
that field with whatever gage reading is cached, which is a real value but not a reproducible one:
it lands in the artifact as an unrelated diff on the next person's run.

## Air emissions scenarios (`<slug>.air-*.scenario.yaml`)

Evaluated backup-generation emissions scenarios (epic #1172, Tier-0), written by
`watermark air scenarios` (`watermark.air.scenario`) and slug-prefixed so a sibling site
never clobbers Lima's. Each rolls fleet annual tonnage against the air permit's
synthetic-minor NSR caps.

| File | What |
|---|---|
| `lima.air-baseline.scenario.yaml` | Readiness-testing baseline (idle load, 100 hr/yr) — compliant. |
| `lima.air-reliability_dispatch_event_central.scenario.yaml` | Event-anchored dispatch at the `[inference]` central intra-window duty (~18 hr/yr) — within caps. |
| `lima.air-reliability_dispatch_event_high.scenario.yaml` | Event-anchored dispatch at the captured PJM §202(c) order's `[verified]` full 72-hour authorized-window ceiling — **breaches** the 235.62 tpy synthetic-minor NOx cap (311 tpy). |

## Conventions

Every input carries a `source` tag (`assumption` vs. measured/derived) and a
`citation`/`confidence` — keep these honest. An `assumption` is a stated modeling
input, not a fact; surface it as such in any report. Add a new scenario by copying
the structure and adjusting the tagged inputs.
