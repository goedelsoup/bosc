import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

const tmpDirs: string[] = [];

function makeBundle(timeline: object[]): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-spine-"));
  tmpDirs.push(dir);
  const feeds = [
    {
      name: "timeline",
      path: "timeline.json",
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: timeline.length,
    },
  ];
  writeFileSync(
    join(dir, "manifest.json"),
    JSON.stringify({
      bundle_version: "test",
      contract_version: "1.4",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: 0,
      feeds,
    }),
  );
  writeFileSync(join(dir, "timeline.json"), JSON.stringify(timeline));
  return dir;
}

async function loadSpine(dir: string): Promise<typeof import("./walkTimeline")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./walkTimeline");
}

const EVENT = (date: string) => ({
  date,
  category: "x",
  title: "t",
  ref: "r",
  parties: [],
  source: "s",
  also_sources: [],
});

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("buildWalkSpine (#225)", () => {
  it("renders four milestones in the confidentiality-first order", async () => {
    const { buildWalkSpine } = await loadSpine(makeBundle([]));
    const spine = buildWalkSpine();
    expect(spine.milestones.map((m) => m.kind)).toEqual(["confidential", "approval", "land", "reveal"]);
  });

  it("present-checks the dated milestones against the timeline feed", async () => {
    const { buildWalkSpine } = await loadSpine(
      makeBundle([EVENT("2025-05-27"), EVENT("2025-07-10"), EVENT("2025-08-13"), EVENT("2024-01-01")]),
    );
    const spine = buildWalkSpine();
    expect(spine.totalEvents).toBe(4);
    // The three sequence beats resolve to feed events; the dated reveal is an
    // annotation (the AEDG release isn't a timeline event), so it stays out of feed.
    for (const m of spine.milestones.filter((x) => x.kind !== "reveal")) {
      expect(m.inFeed).toBe(true);
    }
    expect(spine.milestones.find((m) => m.kind === "reveal")?.inFeed).toBe(false);
  });

  it("never claims a feed event the bundle doesn't have", async () => {
    const { buildWalkSpine } = await loadSpine(makeBundle([EVENT("2025-05-27")]));
    const spine = buildWalkSpine();
    // Only 2025-05-27 is present; the other dated beats are not in-feed.
    const inFeed = spine.milestones.filter((m) => m.inFeed).map((m) => m.date);
    expect(inFeed).toEqual(["2025-05-27"]);
  });

  it("confirms the customer is Google [verified], with annotation-not-a-node as a graph-method note", async () => {
    const { buildWalkSpine } = await loadSpine(makeBundle([]));
    const reveal = buildWalkSpine().milestones.find((m) => m.kind === "reveal");
    // The customer question is closed, not open: verified Google.
    expect(reveal?.detail).toMatch(/\[verified\]/);
    expect(reveal?.detail).toMatch(/Google/);
    // "annotation, not a node" stays — but framed as a graph-method choice.
    expect(reveal?.detail).toMatch(/annotation, not a node/i);
  });
});
