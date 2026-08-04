# Per-site instance notes

One file per site whose copy of this dataset has published findings, named for that site's
registry slug (`lima.md` → the `lima` site). The dataset README beside this directory carries
what is true wherever the connector is pointed; a note here carries what one county's
reduction actually turned out to say — the facilities, the screen, the corridor.

A site without a note is the normal case: it renders the README over its own data. A note is
never inherited, and one is never written for a site that does not own the dataset.

This README is **not** a note — a filename here is a site slug, so both readers skip it by
name (`instanceSites()` in `@watermark/core/reference`, and the `referenceNotes` content
collection's glob).
