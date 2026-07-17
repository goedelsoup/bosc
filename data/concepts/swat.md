---
title: SWAT
kind: term
aliases: ["Soil and Water Assessment Tool"]
tags: [hydrology, modeling]
summary: A watershed-scale model that simulates runoff, sediment, and nutrient loading across a basin to support TMDL and land-use analysis.
related: [tmdl, total-phosphorus, huc]
---

The **Soil and Water Assessment Tool** is a watershed model that routes rainfall
through a basin's soils, land cover, and channels to estimate runoff, sediment, and
nutrient loads over time. It works at the [[HUC]] scale, dividing a basin into
subwatersheds so land-use change in one area can be traced to loading downstream.

SWAT is the kind of model that stands behind a nutrient [[total maximum daily load]]:
it apportions a reach's [[total phosphorus]] and nitrogen load among its sources,
which is what a load budget and its allocations are built on. The platform treats a
SWAT output as a modeled [inference] — useful for attributing and comparing loads,
but distinct from a measured [[discharge monitoring report]] value, and only as good
as the land-cover and soil inputs it was run on.
