// Where an /ask citation actually lands (#1890), end to end over the committed bundle.
//
// `askRender.test.ts` covers `citationHref`'s branches on hand-written citations. Every one of
// those assertions passed for as long as the deep link was dead: the renderer tested `source` for a
// leading `data/documents/` prefix, the fixture obligingly had one, and no unit the index emits ever
// has — so the branch never executed against real data and the "verify against the source bytes"
// link (#328) silently resolved to the group page instead, from the day it was written.
//
// A fixture cannot catch that, because the fixture is the thing that was wrong. This runs the real
// chain instead: `buildAskIndex` → `candidateCitations` (the same projection `/api/ask` streams to
// the page, which is where `doc_rel` has to survive) → `citationHref` → the permalinks
// `network/[site]/doc/[id].astro` actually mints.
//
// It lives here rather than in `core` because that chain crosses the package boundary in the one
// direction it can: `functions` depends on `core`, so only this side can see both halves.
//
// `/ask-index.json` is built from the reference site's bundle alone — its unit URLs come from the
// Lima-pinned `siteUrl` — so one site is the whole population here, not a sample of it.
import { describe, expect, it } from "vitest";
import { buildAskIndex } from "@watermark/core/askIndex";
import { hasFeed, loadFeed, runWithSite } from "@watermark/core/bundle";
import { isRoutableDoc } from "@watermark/core/docRouting";
import { documentId } from "@watermark/core/documentId";
import type { DocumentCollectionItem } from "@watermark/core/feeds";
import { LIMA_SLUG, siteBase } from "@watermark/core/routes";
import { citationHref } from "@watermark/core/askRender";
import { candidateCitations } from "@watermark/functions/api/_lib/ask";
import type { AskUnit, Hit } from "@watermark/functions/api/_lib/retrieval";

const SITE = siteBase(LIMA_SLUG);

const { units, routable } = runWithSite(LIMA_SLUG, () => ({
  units: buildAskIndex() as AskUnit[],
  // Exactly the set `network/[site]/doc/[id].astro` builds pages for — catalogued minus the OS
  // exhaust `isRoutableDoc` withholds. A rel outside it has no page to link to.
  routable: new Set(
    (hasFeed("documents") ? loadFeed<DocumentCollectionItem[]>("documents") : [])
      .flatMap((c) => c.entries)
      .filter(isRoutableDoc)
      .map((e) => e.rel),
  ),
}));

/** Every unit as the page receives it — through the Function's own projection, not a copy of it. */
const citations = candidateCitations(units.map((unit): Hit => ({ unit, score: 1 })));
const deepLinked = citations.filter((c) => c.doc_rel && routable.has(c.doc_rel));

describe("ask citations over the committed reference bundle (#1890)", () => {
  it("has citations to deep-link at all — the property that was silently false", () => {
    // Without this the cases below are vacuously true, which is precisely the state the code
    // shipped in: a filter matching nothing satisfies "every match is well-formed". The floors are
    // loose because the corpus grows; what must never happen is either reaching zero.
    expect(citations.length).toBeGreaterThan(100);
    expect(deepLinked.length).toBeGreaterThan(0);
  });

  it("carries doc_rel through the projection the page actually receives", () => {
    // The field existed on the unit for #1590 and simply wasn't copied onto the citation, so the
    // renderer could not have used it even had it looked. This is that copy, asserted.
    const withRel = units.filter((u) => u.doc_rel);
    expect(citations.filter((c) => c.doc_rel).length).toBe(withRel.length);
  });

  it("sends each deep-linkable citation to a permalink the build mints", () => {
    for (const c of deepLinked) {
      expect(citationHref(c, "/")).toBe(`${SITE}/doc/${documentId(c.doc_rel as string)}/`);
    }
  });

  it("never emits the site-less permalink, which has no route", () => {
    // `/doc/<id>/` is what the old code produced; the only route serving a permalink is
    // `/network/<site>/doc/<id>/`. Asserted over every citation, deep-linked or not.
    for (const c of citations) expect(citationHref(c, "/").startsWith("/doc/")).toBe(false);
  });

  it("leaves every other citation on the page its unit lives on", () => {
    const rest = citations.filter((c) => !c.doc_rel || !routable.has(c.doc_rel));
    expect(rest.length).toBeGreaterThan(0);
    for (const c of rest) expect(citationHref(c, "/")).toBe(c.url);
  });
});
