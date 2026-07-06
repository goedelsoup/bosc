import { describe, expect, it } from "vitest";
import { loadFeed } from "./bundle";
import {
  KIND_META,
  LEAD_FILTERS,
  type Lead,
  RECENTLY_CLOSED,
  STATUS_META,
  leadCount,
  leadStats,
} from "./leads";

// The lead DATA now lives in the per-site `leads` bundle feed (#796), not a frontend constant —
// so the data-discipline checks run against Lima's committed feed (the `sites/lima`
// fixture), and the presentation helpers are exercised against it.
const LEADS = loadFeed<Lead[]>("leads", "lima");

describe("leads feed + helpers", () => {
  it("has leads, all with a real source citation (data discipline — no unsourced gap)", () => {
    expect(LEADS.length).toBeGreaterThan(0);
    for (const l of LEADS) {
      expect(l.source.trim().length).toBeGreaterThan(0);
      expect(l.title.trim().length).toBeGreaterThan(0);
      expect(l.detail.trim().length).toBeGreaterThan(0);
    }
  });

  it("has unique ids", () => {
    const ids = LEADS.map((l) => l.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every lead uses a known kind/status/tag (vocab is closed)", () => {
    for (const l of LEADS) {
      expect(KIND_META[l.kind]).toBeDefined();
      expect(STATUS_META[l.status]).toBeDefined();
      expect(["open", "inference"]).toContain(l.tag);
    }
  });

  it("filter counts partition the leads (sum of kind buckets === total)", () => {
    const kinds = LEAD_FILTERS.filter((f) => f.key !== "all").map((f) => f.key as Lead["kind"]);
    const sum = kinds.reduce((a, k) => a + leadCount(LEADS, k), 0);
    expect(sum).toBe(LEADS.length);
    expect(leadCount(LEADS, "all")).toBe(LEADS.length);
  });

  it("stats are derived from the leads + the closed-count argument", () => {
    const stats = leadStats(LEADS, RECENTLY_CLOSED.length);
    const open = stats.find((s) => s.label === "open leads");
    const withheld = stats.find((s) => s.label === "withheld / sealed");
    expect(open?.n).toBe(LEADS.length);
    expect(withheld?.n).toBe(LEADS.filter((l) => l.status === "withheld").length);
    expect(stats.find((s) => s.label === "closed recently")?.n).toBe(RECENTLY_CLOSED.length);
  });

  it("linked issues, when present, are positive integers", () => {
    for (const l of LEADS) {
      if (l.issue != null) {
        expect(Number.isInteger(l.issue)).toBe(true);
        expect(l.issue).toBeGreaterThan(0);
      }
    }
  });
});
