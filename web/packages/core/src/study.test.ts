import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { loadFeed } from "./bundle";
import {
  chapterAvailability,
  chapterNumber,
  type ChapterStatus,
  IMPACT_STUDY_FEED,
  type ImpactStudyFeedRow,
  STUDY_CHAPTERS,
  STUDY_PARTS,
  studyChapter,
  studyChapterModel,
  studyGapLeads,
  studyHref,
  studyStatusSummary,
  studyToc,
} from "./study";

// The study reads the committed per-site bundles (`web/sites/<slug>/`), so these verdicts run
// against real reference data — the three pinned fixtures already exercise data / partial /
// gap (fort-wayne's zero-row hydrology-scenarios and unknown cooling; urbana's screening-only
// facility), and defiance is the facility-less backdrop case. No synthetic fixtures needed.

const statusOf = (id: string, slug: string): ChapterStatus =>
  chapterAvailability(studyChapter(id), slug).status;

describe("study registry — invariants", () => {
  it("chapter ids are unique, non-empty, and never the reserved `f` segment", () => {
    const ids = STUDY_CHAPTERS.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id.length).toBeGreaterThan(0);
      // `/study/f/<facility-key>/…` is reserved for facility-scoped studies (multi-project).
      expect(id).not.toBe("f");
      expect(id).toMatch(/^[a-z][a-z-]*$/);
    }
  });

  it("every chapter belongs to a declared part, and every part has chapters", () => {
    const partIds = new Set(STUDY_PARTS.map((p) => p.id));
    for (const c of STUDY_CHAPTERS) expect(partIds.has(c.part)).toBe(true);
    for (const p of STUDY_PARTS) {
      expect(STUDY_CHAPTERS.some((c) => c.part === p.id)).toBe(true);
    }
  });

  it("every chapter carries the gap grammar and site-relative reference paths", () => {
    for (const c of STUDY_CHAPTERS) {
      expect(c.gap.wouldScreen.length).toBeGreaterThan(0);
      expect(c.gap.missingRecord.length).toBeGreaterThan(0);
      for (const r of c.references) expect(r.path.startsWith("/")).toBe(true);
    }
  });

  it("numbers chapters continuously and builds site-rooted hrefs", () => {
    expect(chapterNumber(STUDY_CHAPTERS[0].id)).toBe(1);
    expect(chapterNumber(STUDY_CHAPTERS[STUDY_CHAPTERS.length - 1].id)).toBe(STUDY_CHAPTERS.length);
    expect(studyHref("lima")).toBe("/network/american-sugar-creek-allen-co/study/");
    expect(studyHref("fort-wayne", "water-supply")).toBe("/network/fort-wayne/study/water-supply");
  });
});

describe("study verdicts — lima (reference: the data-dominant strip)", () => {
  it.each([
    ["method", "data"],
    ["project", "data"], // permit-grounded load ⇒ facility domain live
    ["water-supply", "data"], // disclosed evaporative tower — no bracket
    ["discharge", "data"],
    ["heat", "data"], // the merged thermal feed
    ["groundwater", "data"], // drawdown + dewatering both on the record
    ["stormwater", "data"], // the routed reach network (reference-only today)
    ["air", "data"],
    ["labor", "data"],
    ["power", "data"], // instrument-grounded load ⇒ demand pressure renders
    ["fiscal", "gap"], // designed gap: no abatement instrument on the record anywhere yet
    ["balance", "data"], // every screened chapter is on the record
    ["missing", "data"],
  ] as const)("%s → %s", (id, expected) => {
    expect(statusOf(id, "lima")).toBe(expected);
  });

  it("water composer carries the worst-case draw, the cited floor, and the bound caveat", () => {
    const m = studyChapterModel("water-supply", "lima");
    expect(m.facilityKey).toBe("project-bosc");
    const labels = m.stats.map((s) => s.label);
    expect(labels).toContain("Worst-case consumptive draw");
    expect(labels).toContain("Receiving low flow (7Q10)");
    // The draw is modeled ⇒ [inference]; the floor is cited ⇒ [verified]. Never swapped.
    expect(m.stats.find((s) => s.label.startsWith("Worst-case"))?.evidence).toBe("inference");
    expect(m.stats.find((s) => s.label.startsWith("Receiving"))?.evidence).toBe("verified");
    expect(m.caveats.join(" ")).toMatch(/worst-case/i);
    expect(m.gaps).toEqual([]); // cooling disclosed — no bracket ask
  });

  it("fiscal renders as the finding even on the reference build", () => {
    const m = studyChapterModel("fiscal", "lima");
    expect(m.status).toBe("gap");
    expect(m.gaps[0]?.missingRecord).toMatch(/abatement/);
  });
});

describe("study verdicts — fort-wayne (live campus, thin water record)", () => {
  it("water-supply is a GAP: the feed is present but carries zero rows", () => {
    // Never `hasFeed` alone — fort-wayne ships `hydrology-scenarios` with count 0.
    expect(statusOf("water-supply", "fort-wayne")).toBe("gap");
  });

  it("the water gap names the cooling disclosure among the asks (facility cooling unknown)", () => {
    const m = studyChapterModel("water-supply", "fort-wayne");
    expect(m.status).toBe("gap");
    expect(m.gaps.map((g) => g.missingRecord).join(" ")).toMatch(/cooling/i);
  });

  it.each([
    ["project", "data"], // Title V permit grounds the load
    ["discharge", "partial"], // baseline burden (rsei) only — no project discharge screen
    ["heat", "gap"],
    ["groundwater", "data"], // the drawdown screen is on the record
    // §II·7 un-gated by #1806: fort-wayne committed its own navigated reach network (the
    // Three Rivers confluence), so the chapter reads its geometry instead of the designed
    // gap. The routed-hydrograph stays absent (geometry-grade table, no cited catchments).
    ["stormwater", "data"],
    ["air", "gap"],
    ["labor", "data"],
    ["power", "data"],
    ["balance", "partial"],
  ] as const)("%s → %s", (id, expected) => {
    expect(statusOf(id, "fort-wayne")).toBe(expected);
  });
});

describe("study verdicts — urbana (confirmed project, screening-only record)", () => {
  it("project is PARTIAL: the load is a screening bracket, not an instrument", () => {
    const { status, reasons } = chapterAvailability(studyChapter("project"), "urbana");
    expect(status).toBe("partial");
    expect(reasons.join(" ")).toMatch(/screening bracket/);
  });

  it("power is PARTIAL and carries the load-instrument ask as a gap panel", () => {
    const m = studyChapterModel("power", "urbana");
    expect(m.status).toBe("partial");
    expect(m.gaps.map((g) => g.missingRecord).join(" ")).toMatch(/air permit|interconnection/);
    // The backdrop still stands — it describes the place.
    expect(m.stats.find((s) => s.label === "Serving utility")).toBeTruthy();
  });

  it("fiscal carries the disclosed investment as a [reference]-register caveat, not a stat", () => {
    const m = studyChapterModel("fiscal", "urbana");
    expect(m.status).toBe("gap");
    expect(m.stats).toEqual([]);
    expect(m.caveats.join(" ")).toMatch(/\$1\.0B/);
  });

  it("water-supply is a gap (zero scenario rows), never a lock", () => {
    expect(statusOf("water-supply", "urbana")).toBe("gap");
  });
});

describe("study verdicts — defiance (facility-less backdrop: the study still exists)", () => {
  it.each([
    ["method", "data"],
    ["project", "gap"], // "no disclosed project" IS the front-matter finding
    ["water-supply", "na"], // project-dependent ⇒ watch state, not a scolding gap
    ["discharge", "partial"], // the receiving water's existing burden is real content
    ["heat", "na"],
    ["groundwater", "na"],
    ["stormwater", "na"],
    ["air", "na"],
    ["labor", "data"], // the backdrop floor is the proof the study isn't a gap generator
    ["power", "partial"], // the chain stands on its own; no campus share is fabricated
    ["fiscal", "na"],
    ["balance", "na"],
    ["missing", "data"],
  ] as const)("%s → %s", (id, expected) => {
    expect(statusOf(id, "defiance")).toBe(expected);
  });

  it("power renders the place's chain with no fabricated campus share", () => {
    const m = studyChapterModel("power", "defiance");
    expect(m.stats.find((s) => s.label === "Serving utility")).toBeTruthy();
    expect(m.stats.find((s) => s.label.startsWith("Campus share"))).toBeUndefined();
    expect(m.gaps).toEqual([]); // no facility ⇒ no instrument ask either
  });
});

describe("the curated gap→lead joins never drift off the board", () => {
  // The curation's ONE owner is the Python projector (#1804), which refuses a dangling
  // join at export — this pins the SHIPPED rows to the committed board from the consumer
  // side, so a hand-edited bundle can't smuggle one past either.
  it("every shipped lead id names a real chapter and a real lead in lima's committed feed", () => {
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, "lima");
    const known = new Set(loadFeed<{ id: string }[]>("leads", "lima").map((l) => l.id));
    const joined = rows.filter((r) => (r.lead_ids?.length ?? 0) > 0);
    expect(joined.length).toBeGreaterThan(0); // lima curates 8 chapters — never silently empty
    for (const row of joined) {
      expect(() => studyChapter(row.chapter)).not.toThrow();
      for (const id of row.lead_ids ?? []) {
        expect(known.has(id), `lima/${row.chapter}: lead "${id}" is not on the board`).toBe(true);
      }
    }
    // `studyGapLeads` is the thin reader of those rows (the annex's residual-asks register).
    expect(studyGapLeads("lima", "fiscal")).toEqual(["PRR-04", "GH-35"]);
    expect(studyGapLeads("urbana", "fiscal")).toEqual([]);
  });

  it("a chapter's rendered gaps carry the curated joins (lima fiscal → the withheld CBA)", () => {
    const m = studyChapterModel("fiscal", "lima");
    expect(m.gaps[0]?.leadIds).toEqual(["PRR-04", "GH-35"]);
    // Uncurated sites keep clean panels — never a borrowed or fuzzy-matched join.
    const u = studyChapterModel("fiscal", "urbana");
    expect(u.gaps[0]?.leadIds ?? []).toEqual([]);
  });
});

describe("studyToc / studyStatusSummary — the cover strip's model", () => {
  it("groups every chapter under its part with a verdict and an href", () => {
    const toc = studyToc("lima");
    expect(toc.map((p) => p.part.id)).toEqual(["project", "environment", "economy", "annex"]);
    const flat = toc.flatMap((p) => p.chapters);
    expect(flat.length).toBe(STUDY_CHAPTERS.length);
    for (const ch of flat) {
      expect(ch.href).toContain("/study/");
      expect(["data", "partial", "gap", "na"]).toContain(ch.status);
    }
  });

  it("summarizes verdict counts for the home cards", () => {
    const lima = studyStatusSummary("lima");
    expect(lima.total).toBe(STUDY_CHAPTERS.length);
    expect(lima.data + lima.partial + lima.gap + lima.na).toBe(lima.total);
    expect(lima.data).toBeGreaterThan(lima.gap); // the reference build reads data-dominant
    const defiance = studyStatusSummary("defiance");
    expect(defiance.na).toBeGreaterThan(0); // watch states, not scolding gaps
  });
});

describe("the impact-study feed seam — a shipped feed is preferred wholesale", () => {
  // A synthetic bundle whose ONLY content is an `impact-study` feed row: when a future Python
  // export ships per-chapter models, the frontend must render them instead of composing.
  let dir: string;

  beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), "study-seam-"));
    const slugDir = join(dir, "seamtest");
    mkdirSync(join(slugDir, "feeds"), { recursive: true });
    // A decoy row for ANOTHER facility rides first: the lookup must match the exact
    // (chapter, facility_key) pair — a null key never wildcards onto some campus's study.
    const decoy: ImpactStudyFeedRow = {
      chapter: "power",
      facility_key: "some-other-campus",
      model: {
        id: "power",
        facilityKey: "some-other-campus",
        status: "gap",
        statusReasons: ["the WRONG facility's row"],
        stats: [],
        gaps: [],
        caveats: [],
      },
    };
    const row: ImpactStudyFeedRow = {
      chapter: "power",
      facility_key: null,
      model: {
        id: "power",
        facilityKey: null,
        status: "data",
        statusReasons: ["from the shipped feed"],
        stats: [],
        gaps: [],
        caveats: [],
      },
    };
    writeFileSync(join(slugDir, "feeds", "impact-study.json"), JSON.stringify([decoy, row]));
    writeFileSync(
      join(slugDir, "manifest.json"),
      JSON.stringify({
        site: "seamtest",
        bundle_version: "0",
        contract_version: "1.41.0",
        generated_at: "2026-01-01T00:00:00Z",
        feed_count: 1,
        row_total: 2,
        feeds: [
          {
            name: "impact-study",
            path: "feeds/impact-study.json",
            media_type: "application/json",
            schema: "schemas/impact-study.schema.json",
            kind: "collection",
            count: 2,
          },
        ],
      }),
    );
    vi.stubEnv("WATERMARK_BUNDLE_DIR", dir);
  });

  afterAll(() => {
    vi.unstubAllEnvs();
    rmSync(dir, { recursive: true, force: true });
  });

  it("prefers the feed row over the TS composer", () => {
    const m = studyChapterModel("power", "seamtest");
    expect(m.statusReasons).toEqual(["from the shipped feed"]);
    expect(m.status).toBe("data");
  });
});
