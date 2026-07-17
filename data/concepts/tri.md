---
title: TRI
kind: term
aliases: [Toxics Release Inventory]
tags: [environment, data-source]
summary: EPA's annual, facility-level inventory of reported toxic-chemical releases to air, water, and land — the data behind the RSEI risk model.
related: [rsei, echo, pfas]
---

The **Toxics Release Inventory** is EPA's annual, self-reported accounting of toxic
chemicals released or transferred by industrial and federal facilities above
reporting thresholds. Each facility files quantities by chemical and medium — air,
water, land — creating a long, comparable public time series of who released what,
where.

TRI is a raw inventory of *pounds*, not of risk: a large release of a low-toxicity
chemical and a small release of a potent one look different on paper but not in
proximity to people. That gap is exactly what the [[RSEI]] model closes, weighting TRI
quantities by toxicity and population exposure. The platform uses TRI as the neutral,
[reference] baseline of a site's release profile, and watches the list expand as newly
regulated compounds like some [[PFAS]] are phased into reporting.
