---
site: lima
title: The corridor LEI watchlist at Lima — Allen County, OH
---

Lima's pinned watchlist, resolved against GLEIF by the
[method the dataset README describes](../README.md#method-litigation-discipline). The
entities are here because the Allen County, OH record named them — the RSEI facility
parents and the corridor's defense anchor — not because a search surfaced them.

## What the registry confirmed

- **General Dynamics Land Systems Inc.** (`875500ULXB4CYQSJVA03`) reports its ultimate
  parent as **General Dynamics Corporation** (`9C1X8XOOTYY2FNYTVH06`) — an independent
  registry confirming the GDLS↔GD ownership behind the JSMC operator (the
  [RSEI](../../rsei/instances/lima.md) #4 Allen County facility by Score, and the
  [defense-contractor scan](../../allen-gis/README.md)).
- **Cenovus Energy Inc.** (`254900LJGL2N2XEMD470`) is the post-2021 successor to Husky
  Energy, the RSEI **Lima Refining Co** parent.
- **INEOS USA LLC** is pinned to the Delaware entity (`549300TWZ86K81VO8O17`) by exact
  legal-name match — deliberately distinct from the Belgian INEOS parent a fuzzy search
  surfaces first. This is the pin-by-ID rule doing the work it exists for.
- The remaining watchlist entities are RSEI Allen County facility parents (Marathon,
  Ford, Dana, Textron, P&G, Shell); the [RSEI instance](../../rsei/instances/lima.md)
  cross-links the two datasets.

A reported parent that returns **404** is recorded as absent, which is not a claim that no
parent exists — see the README's method section. Nothing on this list is a fuzzy match.
