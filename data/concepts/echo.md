---
title: ECHO
kind: term
aliases: ["Enforcement and Compliance History Online"]
tags: [environment, enforcement, data-source]
summary: EPA's public database of facility permits, inspections, violations, and enforcement actions across its major programs.
related: [rsei, tri, snc, npdes, dmr, epa]
---

**Enforcement and Compliance History Online** is the [[EPA]] portal that consolidates
a facility's regulatory record — its permits, inspections, reported violations, and
formal enforcement — across the water, air, and waste programs. It ingests the
self-reported [[discharge monitoring report]] data and surfaces derived flags like
[[significant non-compliance]], all keyed to a facility identifier.

ECHO is the platform's workhorse for facility compliance because it is public,
queryable, and national — an outside analyst can reconstruct a discharger's history
without a records request. Its data seeds several of the platform's reference
datasets, including the [[NPDES]] inventory and the facility list behind the [[RSEI]]
risk screen. An ECHO record is [reference] as pulled; the platform dates and caches it
so a compliance claim stays anchored to the snapshot it was drawn from.
