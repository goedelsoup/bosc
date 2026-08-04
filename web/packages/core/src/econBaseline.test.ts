import { describe, expect, it } from "vitest";
import {
  employmentChange,
  rankByEmployment,
  reconcileEmployment,
  reportedSeries,
  sumEmployment,
} from "./econBaseline";
import type { EconOwnership, EconSector, EconTrendPoint, ProvenancedValue } from "./feeds";

// Every committed site bundle today reports every sector, every year and every ownership slice,
// so none of the absent branches below is exercised by real data — which is exactly why the
// zero-flooring survived to #1918. These fixtures are the missing measurement.
const pv = (value: number | null): ProvenancedValue => ({ value, unit: "jobs", source: "connector" });

const sector = (naics: string, jobs: number | null): EconSector => ({
  naics,
  sector_name: `Sector ${naics}`,
  annual_avg_employment: pv(jobs),
});

const ownership = (code: string, jobs: number | null): EconOwnership => ({
  ownership: code,
  ownership_name: `Ownership ${code}`,
  annual_avg_employment: pv(jobs),
});

const year = (y: number, employment: number | null, establishments?: number | null): EconTrendPoint => ({
  year: y,
  total_employment: pv(employment),
  establishments: establishments === undefined ? null : pv(establishments),
});

describe("rankByEmployment", () => {
  it("ranks reported sectors largest first", () => {
    const ranked = rankByEmployment([sector("31", 3000), sector("62", 9452), sector("44", 5100)]);
    expect(ranked.map((s) => s.naics)).toEqual(["62", "44", "31"]);
  });

  it("leaves an absent sector unranked at the tail, behind a genuinely reported zero", () => {
    const ranked = rankByEmployment([sector("11", null), sector("62", 9452), sector("21", 0)]);
    // The suppressed sector sorts last; the reported zero keeps its place ahead of it, which the
    // old `?? 0` comparator could not distinguish.
    expect(ranked.map((s) => s.naics)).toEqual(["62", "21", "11"]);
  });

  it("keeps several absent sectors in their original order", () => {
    const ranked = rankByEmployment([sector("11", null), sector("21", null), sector("62", 9452)]);
    expect(ranked.map((s) => s.naics)).toEqual(["62", "11", "21"]);
  });

  it("does not mutate its input", () => {
    const rows = [sector("31", 3000), sector("62", 9452)];
    rankByEmployment(rows);
    expect(rows.map((s) => s.naics)).toEqual(["31", "62"]);
  });
});

describe("sumEmployment", () => {
  it("sums a fully reported set and reports it complete", () => {
    expect(sumEmployment([sector("62", 9452), sector("44", 5100)])).toEqual({
      total: 14552,
      reported: 2,
      missing: 0,
      complete: true,
    });
  });

  it("counts an absent row instead of adding a zero for it", () => {
    const sum = sumEmployment([sector("62", 9452), sector("11", null), sector("44", 5100)]);
    expect(sum).toEqual({ total: 14552, reported: 2, missing: 1, complete: false });
    // The total is a floor, and `complete: false` is what stops a caller from printing it as one.
    expect(sum.complete).toBe(false);
  });

  it("treats an empty set as complete (a sum of nothing is zero, not a gap)", () => {
    expect(sumEmployment([])).toEqual({ total: 0, reported: 0, missing: 0, complete: true });
  });
});

describe("reconcileEmployment", () => {
  const sectors = [sector("62", 9000), sector("44", 5000)];
  const government = [ownership("1", 321), ownership("2", 400), ownership("3", 3400)];

  it("reconciles when the total and every row are reported", () => {
    expect(reconcileEmployment(pv(18700), sectors, government)).toEqual({
      kind: "reconciled",
      sectorJobs: 14000,
      govJobs: 4121,
      totalJobs: 18700,
      residual: 579,
    });
  });

  it("withholds the residual when a sector is absent", () => {
    const r = reconcileEmployment(pv(18700), [...sectors, sector("11", null)], government);
    expect(r).toEqual({ kind: "incomplete", totalJobs: 18700, missing: 1 });
  });

  it("withholds the residual when a government slice is absent", () => {
    const r = reconcileEmployment(pv(18700), sectors, [...government, ownership("5", null)]);
    expect(r).toEqual({ kind: "incomplete", totalJobs: 18700, missing: 1 });
  });

  it("withholds the reconciliation when the county total itself is absent", () => {
    expect(reconcileEmployment(pv(null), sectors, government)).toEqual({
      kind: "incomplete",
      totalJobs: null,
      missing: 0,
    });
    expect(reconcileEmployment(undefined, sectors, government)).toEqual({
      kind: "incomplete",
      totalJobs: null,
      missing: 0,
    });
  });

  it("counts every absent row across both sums", () => {
    const r = reconcileEmployment(
      pv(18700),
      [...sectors, sector("11", null)],
      [...government, ownership("5", null)],
    );
    expect(r).toMatchObject({ kind: "incomplete", missing: 2 });
  });

  it("reconciles a government-less site (no slices is not a gap)", () => {
    expect(reconcileEmployment(pv(14000), sectors, [])).toMatchObject({
      kind: "reconciled",
      govJobs: 0,
      residual: 0,
    });
  });
});

describe("reportedSeries", () => {
  it("keeps only the measured years — an absent one is dropped, never plotted at zero", () => {
    const trend = [year(2020, 49814), year(2021, null), year(2022, 50100)];
    expect(reportedSeries(trend, (t) => t.total_employment)).toEqual([
      { year: 2020, value: 49814 },
      { year: 2022, value: 50100 },
    ]);
  });

  it("reads an optional field, dropping the years that lack it", () => {
    const trend = [year(2020, 49814, 2487), year(2021, 50000), year(2022, 50100, 2510)];
    expect(reportedSeries(trend, (t) => t.establishments)).toEqual([
      { year: 2020, value: 2487 },
      { year: 2022, value: 2510 },
    ]);
  });

  it("keeps a genuinely reported zero", () => {
    expect(reportedSeries([year(2020, 0)], (t) => t.total_employment)).toEqual([{ year: 2020, value: 0 }]);
  });
});

describe("employmentChange", () => {
  it("reads a rise as growth against the first reported year", () => {
    const c = employmentChange([year(2014, 49814), year(2024, 54795)]);
    expect(c).toMatchObject({ direction: "grew", delta: 4981 });
    expect(c?.pct).toBeCloseTo(10.0, 1);
  });

  it("reads a fall as a shrink", () => {
    const c = employmentChange([year(2014, 50000), year(2024, 45000)]);
    expect(c).toMatchObject({ direction: "shrank", delta: -5000 });
    expect(c?.pct).toBeCloseTo(-10.0, 1);
  });

  it("reads an equal two-point series as unchanged, not a 0.0% shrink (#1918)", () => {
    const c = employmentChange([year(2014, 49814), year(2024, 49814)]);
    expect(c).toMatchObject({ direction: "unchanged", delta: 0, pct: 0 });
  });

  it("measures between the first and last REPORTED years, which it names", () => {
    const c = employmentChange([year(2014, null), year(2016, 40000), year(2020, 44000), year(2024, null)]);
    expect(c).toMatchObject({ first: { year: 2016, value: 40000 }, last: { year: 2020, value: 44000 } });
    expect(c?.pct).toBeCloseTo(10.0, 1);
  });

  it("is null when fewer than two years are reported (one point is a level, not a change)", () => {
    expect(employmentChange([year(2014, null), year(2024, 49814)])).toBeNull();
    expect(employmentChange([year(2024, 49814)])).toBeNull();
    expect(employmentChange([])).toBeNull();
  });

  it("withholds the percentage when the first reported year is zero", () => {
    const c = employmentChange([year(2014, 0), year(2024, 500)]);
    expect(c).toMatchObject({ direction: "grew", delta: 500, pct: null });
  });
});
