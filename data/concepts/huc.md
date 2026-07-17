---
title: HUC
kind: term
aliases: ["hydrologic unit code", HUC-8, HUC-12]
tags: [hydrology, watershed]
summary: The USGS nested numeric code that identifies a watershed at a chosen scale, from large subbasins (HUC-8) down to local subwatersheds (HUC-12).
related: [usgs, nwis, swat]
---

A **hydrologic unit code** is the [[USGS]] address for a watershed. The codes nest
by scale: each added pair of digits subdivides the drainage area, so a HUC-8
identifies a subbasin (the working unit for a [[total maximum daily load]]) and a
HUC-12 a local subwatershed of a few dozen square miles.

The HUC is the join key for hydrology in this record. It is how a facility's outfall
is tied to the impaired water it discharges to, how [[NWIS]] gauges and nutrient
loads are rolled up to a consistent drainage area, and how a watershed model like
[[SWAT]] is bounded. Getting the HUC right is what keeps a downstream analysis
anchored to the actual receiving system rather than a nearby but hydrologically
separate one.
