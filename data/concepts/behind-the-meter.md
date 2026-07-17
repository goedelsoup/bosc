---
title: Behind-the-meter
kind: concept
aliases: [BTM, "behind the meter"]
tags: [energy, grid, data-center]
summary: On-site generation that serves a load directly, without that power crossing the utility meter or the public grid.
related: [interconnection-queue, hyperscale-data-center, pjm]
---

**Behind-the-meter** generation sits on the customer's side of the utility meter and
feeds its load directly — gas turbines, engines, fuel cells, or solar paired with
storage — so the power never transacts across the grid. The arrangement lets a large
user self-supply some or all of its demand rather than draw it entirely from the
utility.

For a [[hyperscale data center]], behind-the-meter generation is a way around the
grid's constraints: it can bring a campus online without waiting out the
[[interconnection queue]] or funding the transmission upgrades a full grid connection
would require. But it moves the impact rather than removing it — on-site combustion
becomes an air-permitting question (a [[permit to install]]), and a "behind-the-meter"
plant that also leans on the grid for backup still shows up in [[PJM]]'s planning. The
platform treats a claimed behind-the-meter design as a sourced assumption to verify,
because it changes both the emissions and the grid-cost story.
