import { describe, expect, it } from "vitest";
import type {
  CatalogItem,
  EconomicBaseline,
  EntityNode,
  PersonItem,
  RecordItem,
  TimelineEntry,
} from "./feeds";
import {
  flaggedRecords,
  isoDate,
  newestRefresh,
  recentEvents,
  recordSpan,
  roleTally,
  roleTotal,
  sectorEmployment,
  tally,
  topEntities,
  topSectors,
} from "./hubLede";

const event = (date: string, title: string): TimelineEntry => ({
  date,
  category: "permit",
  title,
  ref: title,
  parties: [],
  source: "src.pdf",
  also_sources: [],
});

describe("recentEvents / recordSpan", () => {
  const entries = [
    event("2024-03-01", "middle"),
    event("2026-01-15", "newest"),
    event("", "undated"),
    event("2019", "year only"),
    event("2021-07-04", "older"),
  ];

  it("returns the newest dated events, newest first", () => {
    expect(recentEvents(entries, 2).map((e) => e.title)).toEqual(["newest", "middle"]);
  });

  it("drops rows the feed left undated rather than ordering them arbitrarily", () => {
    // A bare-year or empty date can't be ranked against a full ISO date, and a lede that says
    // "most recent" must not lead with a row whose position is a guess.
    const titles = recentEvents(entries, 10).map((e) => e.title);
    expect(titles).not.toContain("undated");
    expect(titles).not.toContain("year only");
  });

  it("spans first to last dated event", () => {
    expect(recordSpan(entries)).toEqual({ first: "2021-07-04", last: "2026-01-15" });
  });

  it("has no span when nothing is dated — never a fabricated one", () => {
    expect(recordSpan([event("", "a"), event("2019", "b")])).toBeNull();
    expect(recordSpan([])).toBeNull();
    expect(recentEvents([], 3)).toEqual([]);
  });
});

describe("flaggedRecords", () => {
  const rec = (rel: string, warnings: string[], approx: string[]): RecordItem => ({
    rel,
    group: "permits",
    title: rel,
    warnings,
    fields: {},
    approximate_paths: approx,
    citation: { source: "s" } as RecordItem["citation"],
  });

  it("flags a validation warning or an approximate transcription", () => {
    const flagged = flaggedRecords([
      rec("clean", [], []),
      rec("warned", ["total mismatch"], []),
      rec("approx", [], ["sections.0.quantity"]),
    ]);
    expect(flagged.map((r) => r.rel)).toEqual(["warned", "approx"]);
  });

  it("is empty on an empty feed", () => {
    expect(flaggedRecords([])).toEqual([]);
  });
});

describe("topEntities", () => {
  const ent = (key: string, display: string, roles: Record<string, number>): EntityNode => ({
    key,
    display,
    kind: "org",
    variants: [],
    signals: [],
    roles,
    parcels: [],
    addresses: [],
    sources: [],
  });

  it("ranks by total role appearances, then display name", () => {
    const entities = [
      ent("b", "Beta", { grantee: 2 }),
      ent("a", "Alpha", { grantee: 4, grantor: 1 }),
      ent("c", "Gamma", { grantee: 2 }),
    ];
    expect(topEntities(entities, 3).map((e) => e.display)).toEqual(["Alpha", "Beta", "Gamma"]);
    expect(roleTotal(entities[1])).toBe(5);
  });

  it("does not mutate its input", () => {
    const entities = [ent("b", "Beta", { x: 1 }), ent("a", "Alpha", { x: 9 })];
    topEntities(entities, 2);
    expect(entities.map((e) => e.key)).toEqual(["b", "a"]);
  });

  it("treats a role-less entity as zero rather than throwing", () => {
    expect(roleTotal({ ...ent("z", "Zeta", {}), roles: undefined as never })).toBe(0);
  });
});

describe("topSectors / sectorEmployment", () => {
  const pv = (value: number | null) => ({ value, unit: null, source: null, citation: null });
  const baseline = (sectors: { name: string; lq: number | null; jobs: number }[]): EconomicBaseline => ({
    fips: "39003",
    area_name: "Allen County",
    latest: {
      year: 2024,
      sectors: sectors.map((s) => ({
        naics: s.name,
        sector_name: s.name,
        annual_avg_employment: pv(s.jobs),
        location_quotient: s.lq === null ? null : pv(s.lq),
      })),
    },
    trend: [],
  });

  it("ranks by location quotient, not headcount", () => {
    const eb = baseline([
      { name: "Retail", lq: 0.9, jobs: 9000 },
      { name: "Manufacturing", lq: 2.4, jobs: 6000 },
      { name: "Health care", lq: 1.3, jobs: 8000 },
    ]);
    expect(topSectors(eb, 2).map((s) => s.sector_name)).toEqual(["Manufacturing", "Health care"]);
  });

  it("drops a sector whose LQ the feed omits — an unranked sector can't claim a rank", () => {
    const eb = baseline([
      { name: "Retail", lq: null, jobs: 9000 },
      { name: "Manufacturing", lq: 2.4, jobs: 6000 },
    ]);
    expect(topSectors(eb, 5).map((s) => s.sector_name)).toEqual(["Manufacturing"]);
  });

  it("sums covered employment, and is null with no sectors at all", () => {
    expect(sectorEmployment(baseline([{ name: "Retail", lq: 1, jobs: 9000 }]))).toBe(9000);
    expect(sectorEmployment(baseline([]))).toBeNull();
    expect(sectorEmployment(null)).toBeNull();
    expect(topSectors(null)).toEqual([]);
  });
});

describe("tally / roleTally / newestRefresh", () => {
  const person = (name: string, roles: string[]): PersonItem => ({
    slug: name.toLowerCase(),
    name,
    aliases: [],
    roles,
    affiliations: [],
    expanded: false,
    tags: [],
    sources: [],
    body: "",
  });

  it("tallies roles most-common first, alphabetical on a tie", () => {
    expect(
      roleTally([
        person("A", ["Commissioner", "Trustee"]),
        person("B", ["Commissioner"]),
        person("C", ["Auditor", " "]),
      ]),
    ).toEqual([
      { label: "Commissioner", count: 2 },
      { label: "Auditor", count: 1 },
      { label: "Trustee", count: 1 },
    ]);
  });

  it("caps the tally at n, keeping the most common", () => {
    expect(tally(["a", "a", "b", "b", "c"], 2)).toEqual([
      { label: "a", count: 2 },
      { label: "b", count: 2 },
    ]);
  });

  const cat = (id: string, refreshed: string | null): CatalogItem =>
    ({ id, source: "s", last_refreshed: refreshed }) as CatalogItem;

  it("takes the newest refresh across the rows that carry one", () => {
    // Most catalog rows legitimately carry none — a `static` committed extraction has no
    // refresh cadence — so a null must be skipped, not treated as the newest.
    expect(newestRefresh([cat("a", "2026-02-01"), cat("b", "2026-05-14"), cat("c", null)])).toBe(
      "2026-05-14",
    );
  });

  it("has no refresh date when no row carries one", () => {
    expect(newestRefresh([cat("a", null)])).toBeNull();
    expect(newestRefresh([])).toBeNull();
    expect(tally([], 5)).toEqual([]);
    expect(roleTally([])).toEqual([]);
  });
});

describe("isoDate", () => {
  it("takes the date off an ISO timestamp", () => {
    expect(isoDate("2026-08-04T12:30:00Z")).toBe("2026-08-04");
    expect(isoDate("2026-08-04")).toBe("2026-08-04");
  });

  it("is null for anything that isn't one", () => {
    expect(isoDate("")).toBeNull();
    expect(isoDate(null)).toBeNull();
    expect(isoDate("last Tuesday")).toBeNull();
  });
});
