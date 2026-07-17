---
title: OPC
kind: term
aliases: [opinion of probable cost, "engineer's estimate"]
tags: [procurement, construction]
summary: A design-phase cost estimate for a public project — the engineer's structured projection of what construction will cost, and the artifact this platform reconstructs from source PDFs.
related: [cmar, rfq, rfp]
---

An **opinion of probable cost** is the design engineer's structured estimate of what a
public project will cost to build, prepared before bids come in. It rolls up quantities
and unit prices into sections and subtotals, then adds markups for contingency and soft
costs — a document precise enough to budget against but explicitly an *opinion*, not a
bid.

The OPC is the reference artifact of the platform's extract stage: the six Tetra Tech
roundabout estimates it reconstructs from a scanned bundle are OPCs, and the
extraction model is built to hold any contractor's section-and-markup structure
without hardcoding one firm's taxonomy. Because the OCR text layer of a scanned OPC
garbles digits, its figures are read from the page image, and each extracted value
carries its page provenance — a dollar total is [verified] from the sheet, an
uncertain quantity marked approximate. It is the cost counterpart to how a project is
procured, whether by [[construction manager at risk]] or competitive bid.
