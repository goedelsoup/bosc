# `usace/` — U.S. Army Corps of Engineers regulatory records

**Collection:** federal Clean Water Act §404 / Rivers and Harbors Act records · immutable
source evidence

Corps regulatory files — jurisdictional determinations, nationwide-permit verifications,
individual permits, and the ESA and §106 consultation that rides along with them.

## Layout

Nested **by site**, the same way [`oepa/`](../oepa/) and [`idem/`](../idem/) are: a Corps
file lands under `usace/<site-slug>/`, which the site's corpus scope picks up through the
derived `*/<slug>` prefix (`watermark.sites._eponymous_prefixes`). A file shelved flat here
would land in the reference build's record instead of its own site's.

| Subfolder | District | File | What |
|---|---|---|---|
| [`west-union/`](west-union/) | Huntington (CELRH) | `LRH-2025-00457-OHR` (-Elk Run) | Buck Canyon Site, Sprigg Township, Adams County — AJD/PJD through NWP 39 verification, 2025-05 → 2026-02 |

## Why the Corps matters at these sites

For a campus in an unzoned county, the §404 permit is often the **only** discretionary
approval anyone has to grant — and with it come the two federal consultations that produce
a public record where local government produces none: Endangered Species Act coordination
with USFWS, and National Historic Preservation Act §106 consultation with the State Historic
Preservation Office. At West Union that machinery is what documented three cemeteries inside
a 1,016-acre project area.

Note what a nationwide permit *is*, though: a **general** authorization the Corps verifies a
project fits, not a permit it individually weighs. The record is thorough about streams,
bats and graves, and silent about load, water demand, and who the end user is.
