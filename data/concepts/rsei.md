---
title: RSEI
kind: term
aliases: ["Risk-Screening Environmental Indicators"]
tags: [environment, data-source]
summary: EPA's model that converts Toxics Release Inventory reports into a comparative, toxicity- and exposure-weighted chronic-risk score.
related: [tri, echo, epa]
---

**Risk-Screening Environmental Indicators** is the [[EPA]] model that turns the raw
pounds in the [[TRI]] into a comparative risk score. It weights each reported release
by the chemical's toxicity and models how it disperses and reaches people, so a small
release of a potent compound near a population can outrank a large release of a benign
one far from anyone.

RSEI is a *screening* tool, not a measurement of harm to any individual — its value is
in ranking and trend, letting an analyst compare facilities and watch a site's risk
profile move over time. The platform pulls RSEI as a committed [reference] dataset
scoped to a site's geography, and treats a score as an [inference] about relative
chronic risk rather than a [verified] exposure. Its inputs are only as current as the
TRI year it was run on.
