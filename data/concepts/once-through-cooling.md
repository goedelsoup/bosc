---
title: Once-through cooling
kind: concept
aliases: [open-loop cooling]
tags: [water, cooling, data-center]
summary: A cooling design that withdraws water, passes it once to absorb heat, and returns nearly all of it to the source — warmer but not consumed.
related: [closed-loop-cooling, consumptive-cooling, heat-reuse]
---

**Once-through cooling** draws water, runs it once through a heat exchanger, and
returns almost all of it to the source. Its signature is a large *withdrawal* but a
small *consumption*: the water comes back, chiefly warmer. The environmental question
it raises is thermal — the heat load and intake entrainment — rather than lost flow.

It is the mirror image of [[closed-loop cooling]], and the distinction is decisive
for the water balance. A once-through data center barely dents downstream flow but
adds a thermal load a receiving water may not tolerate at low flow; a recirculating
one withdraws far less yet consumes most of what it takes through evaporation. Which
design an operator chooses therefore determines whether a campus reads as a
[[consumptive cooling]] problem or a thermal one — so the platform keeps the cooling
type an explicit, sourced assumption, not a guess.
