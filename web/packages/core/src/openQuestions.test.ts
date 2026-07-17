import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { OpenQuestionItem } from "./feeds";

// The `open-questions` backlink machinery (#1569): a concept/entity page passes its own names and
// gets back the open questions whose prose *raises* them — the reverse of a `[[wiki link]]`, over a
// feed that names its subjects in prose rather than bracket syntax. Tested against a tmp bundle so
// the whole-phrase matching + gating are exercised without touching a committed feed.

const tmpDirs: string[] = [];

function q(
  id: string,
  question: string,
  detail: string,
  origin: "lead" | "hypothesis" = "lead",
): OpenQuestionItem {
  return { id, origin, question, detail, source: `data/extracted/${id}.yaml` };
}

function manifestWith(rows: OpenQuestionItem[]): object {
  return {
    bundle_version: "test",
    contract_version: "1.27",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: 1,
    row_total: rows.length,
    feeds: [
      {
        name: "open-questions",
        path: "open-questions.json",
        media_type: "application/json",
        schema: "s",
        kind: "collection",
        count: rows.length,
      },
    ],
  };
}

/** A parent dir holding one bundle per slug under `<parent>/<slug>/`. */
function makeSiteBundles(bySlug: Record<string, OpenQuestionItem[] | null>): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-oq-"));
  tmpDirs.push(parent);
  for (const [slug, rows] of Object.entries(bySlug)) {
    const dir = join(parent, slug);
    mkdirSync(dir, { recursive: true });
    // rows === null models a site whose projector shipped no `open-questions` feed at all.
    const manifest = rows
      ? manifestWith(rows)
      : {
          bundle_version: "test",
          contract_version: "1.27",
          generated_at: "2026-01-01T00:00:00Z",
          feed_count: 0,
          row_total: 0,
          feeds: [],
        };
    writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
    if (rows) writeFileSync(join(dir, "open-questions.json"), JSON.stringify(rows));
  }
  return parent;
}

async function load(dir: string) {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  const bundle = await import("./bundle");
  const wiki = await import("./wiki");
  return { bundle, wiki };
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("openQuestionBacklinks — prose backlinks (#1569)", () => {
  const rows: OpenQuestionItem[] = [
    q(
      "OEPA-2DP00130",
      "Public-comment window on the Bosc indirect-discharge permit",
      "Ohio EPA has a draft permit for BISTROZZI LLC routing cooling water to the American-Bath WWTP.",
    ),
    q(
      "SWCD-1",
      "SWCD stormwater review still outstanding",
      "The Soil and Water Conservation District has not produced its file.",
    ),
    {
      ...q(
        "hyp:surveillance:columbus",
        "Open thread — H3 Consumer Surveillance @ columbus",
        "No documented nexus yet for columbus.",
        "hypothesis",
      ),
      hypothesis: "surveillance",
      hypothesis_label: "H3 Consumer Surveillance",
      signal: "watch",
    },
  ];

  it("matches a node's name as a whole phrase across question + detail", async () => {
    const { bundle, wiki } = await load(makeSiteBundles({ lima: rows }));
    const hits = bundle.runWithSite("lima", () => wiki.openQuestionBacklinks(["Ohio EPA", "OEPA"]));
    expect(hits.map((h) => h.id)).toEqual(["OEPA-2DP00130"]);
    expect(hits[0].url).toBe("/wiki/open-questions/#oepa-2dp00130");
    expect(hits[0].origin).toBe("lead");
  });

  it("resolves an entity named only in the detail prose", async () => {
    const { bundle, wiki } = await load(makeSiteBundles({ lima: rows }));
    const hits = bundle.runWithSite("lima", () => wiki.openQuestionBacklinks(["BISTROZZI LLC"]));
    expect(hits.map((h) => h.id)).toEqual(["OEPA-2DP00130"]);
  });

  it("matches a short initialism only as a whole token, never a substring", async () => {
    const { bundle, wiki } = await load(makeSiteBundles({ lima: rows }));
    // "SWCD" (4 chars) qualifies and matches its own row; it must NOT bleed into unrelated prose.
    const swcd = bundle.runWithSite("lima", () => wiki.openQuestionBacklinks(["SWCD"]));
    expect(swcd.map((h) => h.id)).toEqual(["SWCD-1"]);
    // "EPA" (3 chars, not multi-word) is below the specificity floor — no accidental backlink.
    const epa = bundle.runWithSite("lima", () => wiki.openQuestionBacklinks(["EPA"]));
    expect(epa).toEqual([]);
  });

  it("carries the hypothesis origin through for a matrix-cell question", async () => {
    const { bundle, wiki } = await load(makeSiteBundles({ lima: rows }));
    const hits = bundle.runWithSite("lima", () => wiki.openQuestionBacklinks(["Consumer Surveillance"]));
    expect(hits.map((h) => h.id)).toEqual(["hyp:surveillance:columbus"]);
    expect(hits[0].origin).toBe("hypothesis");
  });

  it("returns nothing for a site whose projector shipped no open-questions feed", async () => {
    const { bundle, wiki } = await load(makeSiteBundles({ thin: null }));
    const hits = bundle.runWithSite("thin", () => wiki.openQuestionBacklinks(["Ohio EPA"]));
    expect(hits).toEqual([]);
  });

  it("anchors an id to its slugified form", async () => {
    const { wiki } = await load(makeSiteBundles({ lima: rows }));
    expect(wiki.openQuestionAnchor("hyp:surveillance:columbus")).toBe("hyp-surveillance-columbus");
    expect(wiki.openQuestionAnchor("OEPA-2DP00130")).toBe("oepa-2dp00130");
  });
});
