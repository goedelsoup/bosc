---
title: NWIS
kind: term
aliases: ["National Water Information System"]
tags: [hydrology, data-source]
summary: The USGS system that serves real-time and historical streamflow and water-quality data from the national gauge network.
related: [usgs, 7q10, huc]
---

The **National Water Information System** is the [[USGS]] database and web service
behind the nation's streamgages. It publishes discharge (flow) and stage, plus water
temperature and quality where instrumented, as both a live feed and a long historical
record, each gauge addressed by a site number.

NWIS is the live-flow spine of the water balance. The platform's hydrology
connectors pull gauge records from NWIS to establish a reach's actual flow regime,
and the long record is what a design low flow like the [[7Q10]] is computed from.
Reading flow from a real, dated NWIS gauge — rather than estimating it — is what lets
a receiving-water value be tagged [verified] and joined by [[HUC]] to the facility
under study.
