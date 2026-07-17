import { describe, expect, it } from "vitest";
import type { FactItem } from "./feeds";
import { FACT_METRICS, aggregateFacts, listMetrics, parseGroupBy, resolveMetric } from "./factAggregate";

/** A terse FactItem builder — only the fields the engine reads. */
function fact(partial: Partial<FactItem> & Pick<FactItem, "subject" | "predicate">): FactItem {
  return {
    subject: partial.subject,
    subject_label: partial.subject_label ?? partial.subject,
    subject_kind: partial.subject_kind ?? "facility",
    predicate: partial.predicate,
    value: partial.value ?? null,
    unit: partial.unit ?? null,
    status: partial.status ?? "verified",
    low: partial.low ?? null,
    high: partial.high ?? null,
    feed: partial.feed ?? "facility-power",
    evidence: partial.evidence ?? {
      source_kind: "document",
      confidence: "high",
      page: null,
      verified: true,
    },
  };
}

const LIMA = [
  fact({
    subject: "facility:lima",
    subject_label: "Lima data center",
    predicate: "genset_count",
    value: 114,
    unit: "count",
  }),
  fact({
    subject: "facility:lima",
    subject_label: "Lima data center",
    predicate: "genset_rating",
    value: 2.75,
    unit: "MW",
  }),
];

describe("resolveMetric", () => {
  it("resolves a registered metric key (case-insensitive)", () => {
    expect(resolveMetric("backup_generation_capacity_mw")?.op).toBe("product");
    expect(resolveMetric("BACKUP_GENERATION_CAPACITY_MW")?.key).toBe("backup_generation_capacity_mw");
  });

  it("resolves the generic <op>:<predicate> grammar", () => {
    expect(resolveMetric("sum:total_employment")).toMatchObject({ op: "sum", inputs: ["total_employment"] });
    expect(resolveMetric("mean:avg_weekly_wage")).toMatchObject({ op: "mean", inputs: ["avg_weekly_wage"] });
    expect(resolveMetric("count:genset_count")).toMatchObject({ op: "count", inputs: ["genset_count"] });
    expect(resolveMetric("product:genset_count,genset_rating")).toMatchObject({
      op: "product",
      inputs: ["genset_count", "genset_rating"],
    });
    expect(resolveMetric("count")).toMatchObject({ op: "count", inputs: [] });
    expect(resolveMetric("count:*")).toMatchObject({ op: "count", inputs: [] });
  });

  it("rejects malformed specs", () => {
    expect(resolveMetric("")).toBeNull();
    expect(resolveMetric("nonsense")).toBeNull();
    expect(resolveMetric("product:only_one")).toBeNull(); // a product needs ≥2 factors
    expect(resolveMetric("sum:a,b")).toBeNull(); // sum takes exactly one predicate
  });
});

describe("aggregateFacts — product (the motivating example)", () => {
  it("computes backup_generation_capacity_mw = 114 × 2.75 = 313.5 MW", () => {
    const metric = resolveMetric("backup_generation_capacity_mw")!;
    const [row] = aggregateFacts(LIMA, metric, parseGroupBy("project"));
    expect(row.value).toBe(313.5);
    expect(row.unit).toBe("MW");
    expect(row.derivation).toBe("114 × 2.75 MW");
    expect(row.group).toBe("facility:lima");
    expect(row.group_label).toBe("Lima data center");
    expect(row.evidence_ids).toEqual(["facility:lima/genset_count", "facility:lima/genset_rating"]);
    expect(row.n).toBe(2);
  });

  it("is an inference even when both factors are verified (a derivation is not a document)", () => {
    const metric = resolveMetric("backup_generation_capacity_mw")!;
    const [row] = aggregateFacts(LIMA, metric, "subject");
    expect(LIMA.every((f) => f.status === "verified")).toBe(true);
    expect(row.status).toBe("inference");
    expect(row.caveat).toContain("BACKUP");
  });

  it("scopes to the metric's subject_kind and omits subjects missing a factor", () => {
    const metric = resolveMetric("backup_generation_capacity_mw")!;
    const facts = [
      ...LIMA,
      // a non-facility subject with a colliding predicate — must be ignored
      fact({ subject: "county:39003", subject_kind: "county", predicate: "genset_count", value: 999 }),
      // a second facility missing genset_rating — dropped, flagged in the caveat
      fact({ subject: "facility:x", subject_kind: "facility", predicate: "genset_count", value: 10 }),
    ];
    const rows = aggregateFacts(facts, metric, "subject");
    expect(rows.map((r) => r.group)).toEqual(["facility:lima"]);
    expect(rows[0].caveat).toContain("omitted");
  });

  it("rolls per-subject products up to a coarser group by summing them", () => {
    const metric = resolveMetric("product:genset_count,genset_rating")!;
    const facts = [
      ...LIMA,
      fact({
        subject: "facility:x",
        subject_label: "X",
        predicate: "genset_count",
        value: 100,
        unit: "count",
      }),
      fact({ subject: "facility:x", subject_label: "X", predicate: "genset_rating", value: 2, unit: "MW" }),
    ];
    // Note: an ad-hoc product infers no unit; the roll-up sums the sub-products 313.5 + 200.
    const [row] = aggregateFacts(facts, metric, parseGroupBy("all"));
    expect(row.group).toBe("site");
    expect(row.value).toBe(513.5);
    expect(row.derivation).toContain("313.5 + 200");
    expect(row.evidence_ids).toHaveLength(4);
  });
});

describe("aggregateFacts — sum / count / mean", () => {
  const ECON = [
    fact({
      subject: "sector:39003:62",
      subject_kind: "sector",
      predicate: "annual_avg_employment",
      value: 12000,
      unit: "jobs",
      feed: "economics-baseline",
    }),
    fact({
      subject: "sector:39003:31",
      subject_kind: "sector",
      predicate: "annual_avg_employment",
      value: 20000,
      unit: "jobs",
      feed: "economics-baseline",
    }),
    fact({
      subject: "sector:39003:44",
      subject_kind: "sector",
      predicate: "annual_avg_employment",
      value: 8000,
      unit: "jobs",
      feed: "economics-baseline",
    }),
  ];

  it("sums a single predicate across a whole-site group with a term-by-term derivation", () => {
    const [row] = aggregateFacts(ECON, resolveMetric("sum:annual_avg_employment")!, parseGroupBy("all"));
    expect(row.value).toBe(40000);
    expect(row.unit).toBe("jobs");
    expect(row.derivation).toBe("12000 + 20000 + 8000 = 40000 jobs");
    expect(row.n).toBe(3);
  });

  it("groups a sum by subject_kind", () => {
    const rows = aggregateFacts(ECON, resolveMetric("sum:annual_avg_employment")!, parseGroupBy("kind"));
    expect(rows).toHaveLength(1);
    expect(rows[0].group).toBe("sector");
    expect(rows[0].value).toBe(40000);
  });

  it("counts matching facts", () => {
    const [row] = aggregateFacts(ECON, resolveMetric("count:annual_avg_employment")!, parseGroupBy("all"));
    expect(row.value).toBe(3);
    expect(row.unit).toBe("facts");
    expect(row.derivation).toContain("3 facts");
  });

  it("means a predicate", () => {
    const [row] = aggregateFacts(ECON, resolveMetric("mean:annual_avg_employment")!, parseGroupBy("all"));
    expect(row.value).toBeCloseTo(13333.3333, 3);
    expect(row.derivation).toContain("/ 3 =");
  });

  it("takes the weakest input status and confidence", () => {
    const mixed = [
      fact({
        subject: "x",
        subject_kind: "s",
        predicate: "p",
        value: 1,
        unit: "u",
        status: "verified",
        evidence: { source_kind: "document", confidence: "high", page: null, verified: true },
      }),
      fact({
        subject: "y",
        subject_kind: "s",
        predicate: "p",
        value: 2,
        unit: "u",
        status: "inference",
        evidence: { source_kind: "derived", confidence: "low", page: null, verified: false },
      }),
    ];
    const [row] = aggregateFacts(mixed, resolveMetric("sum:p")!, parseGroupBy("all"));
    expect(row.status).toBe("inference");
    expect(row.confidence).toBe("low");
    expect(row.caveat).toContain("modeled");
  });

  it("truncates a long sum derivation to a bounded term list", () => {
    const many = Array.from({ length: 10 }, (_, i) =>
      fact({ subject: `s${i}`, subject_kind: "s", predicate: "p", value: 1, unit: "u" }),
    );
    const [row] = aggregateFacts(many, resolveMetric("sum:p")!, parseGroupBy("all"));
    expect(row.value).toBe(10);
    expect(row.derivation).toContain("(10 terms)");
  });
});

describe("aggregateFacts — review fixes (#1650)", () => {
  // Finding 4: units resolve per group, and a group mixing units is not summed.
  it("keeps each group's own unit and refuses to sum a mixed-unit group", () => {
    const facts = [
      fact({ subject: "a", subject_kind: "s", predicate: "p", value: 10, unit: "MW", feed: "f1" }),
      fact({ subject: "a", subject_kind: "s", predicate: "p", value: 20, unit: "kW", feed: "f2" }),
      fact({ subject: "b", subject_kind: "s", predicate: "p", value: 5, unit: "MW", feed: "f3" }),
    ];
    // group_by subject: "a" mixes MW + kW (not summable); "b" keeps its own MW (not lost to a).
    const rows = aggregateFacts(facts, resolveMetric("sum:p")!, parseGroupBy("subject"));
    const a = rows.find((r) => r.group === "a")!;
    const b = rows.find((r) => r.group === "b")!;
    expect(a.value).toBeNull();
    expect(a.unit).toBeNull();
    expect(a.derivation).toContain("mixed units");
    expect(a.caveat).toContain("Mixed units");
    expect(b.value).toBe(5);
    expect(b.unit).toBe("MW"); // a consistent group is not dragged to null by its sibling
  });

  it("treats a unitless value as incompatible with a declared unit", () => {
    const facts = [
      fact({ subject: "a", subject_kind: "s", predicate: "p", value: 10, unit: "MW" }),
      fact({ subject: "a", subject_kind: "s", predicate: "p", value: 20, unit: null }),
    ];
    const [row] = aggregateFacts(facts, resolveMetric("sum:p")!, parseGroupBy("all"));
    expect(row.value).toBeNull();
    expect(row.derivation).toContain("mixed units");
  });

  // Finding 3: a product spanning feeds gets an explicit composite feed key, not factors[0].
  it("attributes a cross-feed product to the sorted set of its feeds under group_by feed", () => {
    const facts = [
      fact({ subject: "facility:z", predicate: "genset_count", value: 4, unit: "count", feed: "feed-b" }),
      fact({ subject: "facility:z", predicate: "genset_rating", value: 2.5, unit: "MW", feed: "feed-a" }),
    ];
    const [row] = aggregateFacts(
      facts,
      resolveMetric("product:genset_count,genset_rating")!,
      parseGroupBy("feed"),
    );
    expect(row.group).toBe("feed-a+feed-b"); // sorted, explicit — not silently pinned to one
    expect(row.value).toBe(10);
  });

  // Finding 2: sub-products keep full precision; the aggregate rounds once, after summing.
  it("rounds only after summing sub-products (no per-term rounding drift)", () => {
    const facts = [
      fact({ subject: "a", predicate: "x", value: 0.0001 }),
      fact({ subject: "a", predicate: "y", value: 0.5 }),
      fact({ subject: "b", predicate: "x", value: 0.0001 }),
      fact({ subject: "b", predicate: "y", value: 0.5 }),
    ];
    // Each sub-product is 0.00005. Rounding each to 4dp first would give 0.0001 + 0.0001 =
    // 0.0002; summing full-precision first gives 0.0001 (round(0.0001, 4)).
    const [row] = aggregateFacts(facts, resolveMetric("product:x,y")!, parseGroupBy("all"));
    expect(row.value).toBe(0.0001);
  });

  // Finding 5: a subject whose factors are all present-but-null still counts as omitted.
  it("flags a subject with only null-valued factors as omitted, not silently absent", () => {
    const facts = [
      ...LIMA, // facility:lima computes 313.5
      fact({ subject: "facility:z", subject_kind: "facility", predicate: "genset_count", value: null }),
      fact({ subject: "facility:z", subject_kind: "facility", predicate: "genset_rating", value: null }),
    ];
    const metric = resolveMetric("backup_generation_capacity_mw")!;
    const [row] = aggregateFacts(facts, metric, parseGroupBy("all"));
    expect(row.value).toBe(313.5); // only the valued subject contributes
    expect(row.caveat).toContain("omitted"); // …but the null-factored subject is acknowledged
  });
});

describe("listMetrics + parseGroupBy", () => {
  it("advertises every registered metric", () => {
    const keys = listMetrics().map((m) => m.key);
    expect(keys).toEqual(FACT_METRICS.map((m) => m.key));
    expect(keys).toContain("backup_generation_capacity_mw");
  });

  it("maps friendly group_by aliases", () => {
    expect(parseGroupBy("project")).toBe("subject");
    expect(parseGroupBy("kind")).toBe("subject_kind");
    expect(parseGroupBy("all")).toBe("site");
    expect(parseGroupBy("feed")).toBe("feed");
    expect(parseGroupBy(undefined)).toBe("subject");
  });
});
