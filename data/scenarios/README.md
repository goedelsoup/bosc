# Water-balance scenarios

Named what-if inputs for the hydrology water-balance model (`watermark.hydrology.scenario`).
Each scenario is a committed YAML of tagged inputs (value, unit, `source`, `citation`,
`confidence`, `asof`) that the model runs over.

## Files

| File | What |
|---|---|
| `baseline.scenario.yaml` | Current municipal loop, **no** data-center cooling draw (cooling demand 0.0 MGD). The reference case. |
| `buildout.scenario.yaml` | The corridor build-out case with campus cooling load. |

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
