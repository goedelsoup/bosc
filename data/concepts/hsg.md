---
title: HSG
kind: term
aliases: [hydrologic soil group]
tags: [hydrology, stormwater]
summary: The NRCS A–D classification of a soil by how readily it infiltrates water — a primary input to runoff curve-number modeling.
related: [curve-number, esc, cgp]
---

A **hydrologic soil group** sorts a soil into one of four classes — A, B, C, or D —
by its infiltration rate when thoroughly wet. Group A soils (sand, gravel) soak up
rain and shed little runoff; group D soils (clay, shallow-to-bedrock) infiltrate
poorly and run off fast. The classification comes from the NRCS soil survey.

HSG is the soil half of the runoff calculation: paired with land cover it fixes the
[[curve number]] that sets how much of a storm becomes runoff. It matters twice for
a development record. It decides how sensitive a site is to the impervious cover a
data-center campus adds, and — because the group can shift between survey editions —
choosing the wrong HSG (say C instead of B) silently changes the modeled runoff, a
drift the platform pins by sourcing the group explicitly rather than defaulting it.
