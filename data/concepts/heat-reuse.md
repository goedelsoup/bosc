---
title: Heat reuse
kind: concept
aliases: [waste-heat reuse, heat recovery]
tags: [data-center, cooling, energy, water-balance]
summary: Capturing a data center's rejected thermal energy and redirecting it to on-site or district heating instead of dumping it — a cooling-design axis distinct from how much water the cooling draw consumes.
related: [consumptive-cooling, hyperscale-data-center]
---

**Heat reuse** is the design choice to *recover* a data center's rejected thermal
energy — piping it to on-site heating or a neighboring building / district-heat
loop — rather than *dumping* it through evaporative towers or dry coolers. It is a
third axis on the cooling-design space, orthogonal to the withdraw-vs-consume
question that [[consumptive cooling]] describes: a campus can dump or recover heat
at either end of the water-use band.

The axis matters here for two reasons. First, where recovery displaces evaporative
rejection it couples to the water story — less heat sent to a cooling tower is less
water evaporated. Second, closed-loop **chip cooling** (direct-to-chip liquid loops,
oil-free magnetic-bearing compressors) sits on the efficient, low-water pole and is
now a deployed hyperscale option, not just a spec sheet.

For a [[hyperscale data center]] the reuse choice is a disclosed-design fact, not
something the footprint reveals. It is treated here as an **industry reference**
design lever — bounding the space of what a campus *could* do — and never as a claim
about any watershed point's cooling design, which stays `[open]` until the operator
discloses it. The named-vendor examples (Danfoss heat-reuse modules and Turbocor
compressors in Google data centers) rest on a single promotional source — the
Danfoss–Google strategic-partnership announcement (Jan 2024), catalogued as
`[reference]` in the `heat_reuse` prior of
`data/reference/datacenter-industry/priors.yaml` (which carries the release URL):
it establishes that the technology is real and deployed, not that any particular
campus uses it.
