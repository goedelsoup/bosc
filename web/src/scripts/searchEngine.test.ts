import { describe, expect, it } from "vitest";
import { esc, rank, renderGroups, renderRow, snippet, type SearchDoc } from "./searchEngine";

const doc = (over: Partial<SearchDoc>): SearchDoc => ({
  title: "Untitled",
  url: "/x",
  section: "The record",
  text: "",
  kind: "Record",
  ...over,
});

describe("searchEngine.rank — the shared matcher (#308)", () => {
  const docs: SearchDoc[] = [
    doc({ title: "Limited Warranty Deed", section: "The record", text: "instrument 202508" }),
    doc({ title: "Bistrozzi LLC", section: "Wiki", kind: "Entity", text: "land assembly deed party" }),
    doc({ title: "Timeline event", section: "The record", kind: "Timeline", text: "the deed was recorded" }),
  ];

  it("requires ALL terms to match across title+body", () => {
    expect(rank(docs, "warranty deed").hits.map((d) => d.title)).toEqual(["Limited Warranty Deed"]);
    expect(rank(docs, "warranty nonexistent").hits).toEqual([]);
  });

  it("ranks a title hit ahead of a body-only hit", () => {
    const titles = rank(docs, "deed").hits.map((d) => d.title);
    expect(titles[0]).toBe("Limited Warranty Deed"); // 'deed' in title outranks body matches
    expect(titles).toContain("Bistrozzi LLC");
    expect(titles).toContain("Timeline event");
  });

  it("returns every match (no cap) and an empty list for a blank query", () => {
    expect(rank(docs, "deed").hits.length).toBe(3);
    expect(rank(docs, "   ").hits).toEqual([]);
    expect(rank(docs, "   ").terms).toEqual([]);
  });
});

describe("searchEngine render grammar", () => {
  it("escapes HTML in untrusted fields", () => {
    expect(esc('a<b>"&')).toBe("a&lt;b&gt;&quot;&amp;");
  });

  it("marks the matched term in a snippet", () => {
    expect(snippet("the consumptive draw is large", ["draw"])).toContain("<mark>draw</mark>");
  });

  it("renders a row with kind, title, mono id, evidence dot, and base-prefixed href", () => {
    const html = renderRow(
      doc({
        title: "Deed",
        url: "/network/american-sugar-creek-allen-co/site/records/deeds/",
        id: "2025-08",
        tag: "verified",
      }),
      ["deed"],
      "/app",
    );
    expect(html).toContain('href="/app/network/american-sugar-creek-allen-co/site/records/deeds/"');
    expect(html).toContain('search-row-kind">Record<');
    expect(html).toContain('search-row-id">2025-08<');
    expect(html).toContain("search-row-dot tag-verified");
  });

  it("omits the dot when a row carries no evidence tag", () => {
    expect(renderRow(doc({ tag: undefined }), [], "")).not.toContain("search-row-dot");
  });

  it("groups results by section, preserving first-seen order, with per-group counts", () => {
    const hits = [
      doc({ title: "A", section: "The record" }),
      doc({ title: "B", section: "Wiki" }),
      doc({ title: "C", section: "The record" }),
    ];
    const html = renderGroups(hits, [], "");
    const heads = [...html.matchAll(/search-group-head">([^<]*)</g)].map((m) => m[1].trim());
    expect(heads).toEqual(["The record", "Wiki"]); // record first (first seen), one box each
    expect(html).toContain('search-group-count">2<'); // two record rows merged into one group
  });
});
