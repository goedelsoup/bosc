import { afterEach, describe, expect, it, vi } from "vitest";
import {
  esc,
  makeIndexLoader,
  rank,
  renderAskHandoff,
  renderGroups,
  renderRow,
  snippet,
  type SearchDoc,
  type SiteShard,
} from "./searchEngine";

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

  it("labels a row with its watershed point only when asked (network scope)", () => {
    // Under site scope every row is the same site's, so the chip would be noise on every line;
    // under network scope it is the difference between an Ohio and an Indiana record (#1890).
    const row = doc({ title: "Petition", site: "fort-wayne" });
    const names = new Map([["fort-wayne", "Fort Wayne"]]);
    expect(renderRow(row, [], "", names)).toContain('search-row-site">Fort Wayne<');
    expect(renderRow(row, [], "")).not.toContain("search-row-site");
  });
});

describe("searchEngine scope ranking (#1890)", () => {
  const docs: SearchDoc[] = [
    doc({ title: "Water agreement", site: "lima" }),
    doc({ title: "Water agreement", site: "fort-wayne" }),
    doc({ title: "Water agreement", kind: "Concept", section: "Wiki" }), // network-global
  ];

  it("floats the reader's own site above the other sites' equally-good matches", () => {
    // Widening to the network must ADD results beneath the ones they were already looking at,
    // not bury them.
    const hits = rank(docs, "water agreement", "fort-wayne").hits;
    expect(hits[0].site).toBe("fort-wayne");
  });

  it("leaves the order alone when no site is in play", () => {
    expect(rank(docs, "water agreement").hits.map((d) => d.site)).toEqual(["lima", "fort-wayne", undefined]);
  });
});

describe("searchEngine.makeIndexLoader — the sharded loader (#1890)", () => {
  const SHARDS: SiteShard[] = [
    { slug: "lima", label: "Lima", url: "/network/american-sugar-creek-allen-co/search-index.json" },
    { slug: "fort-wayne", label: "Fort Wayne", url: "/network/fort-wayne/search-index.json" },
  ];
  const row = (site: string): SearchDoc[] => [doc({ title: site, site })];

  const stubFetch = (): string[] => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      seen.push(url);
      const body =
        url === "/search-index.json"
          ? [doc({ title: "Wiki", kind: "Concept" })]
          : row(url.includes("fort-wayne") ? "fort-wayne" : "lima");
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    return seen;
  };

  // `vi.unstubAllGlobals()` does NOT undo a `vi.spyOn`, so a console.error mock left by one case
  // would silence the next one's real failures. Restored explicitly.
  let quiet: ReturnType<typeof vi.spyOn> | null = null;
  const silenceErrors = (): void => {
    quiet = vi.spyOn(console, "error").mockImplementation(() => {});
  };

  afterEach(() => {
    vi.unstubAllGlobals();
    quiet?.mockRestore();
    quiet = null;
  });

  it("site scope loads the network shard plus THIS site's, and no other site's", () => {
    const seen = stubFetch();
    const load = makeIndexLoader("/search-index.json", SHARDS, "fort-wayne");
    return load("site").then((docs) => {
      expect(seen.sort()).toEqual(["/network/fort-wayne/search-index.json", "/search-index.json"].sort());
      expect(docs.map((d) => d.site)).toEqual([undefined, "fort-wayne"]);
    });
  });

  it("network scope loads every site's shard", () => {
    const seen = stubFetch();
    const load = makeIndexLoader("/search-index.json", SHARDS, "fort-wayne");
    return load("network").then((docs) => {
      expect(seen.length).toBe(3);
      expect(
        docs
          .filter((d) => d.site)
          .map((d) => d.site)
          .sort(),
      ).toEqual(["fort-wayne", "lima"]);
    });
  });

  it("fetches each shard at most once across scope changes", () => {
    // Toggling scope on the results page must not re-pull Lima's 3,247-document shard.
    const seen = stubFetch();
    const load = makeIndexLoader("/search-index.json", SHARDS, "lima");
    return load("site")
      .then(() => load("network"))
      .then(() => load("site"))
      .then(() => {
        expect(new Set(seen).size).toBe(seen.length); // no URL fetched twice
        expect(seen.length).toBe(3);
      });
  });

  it("degrades to the shards that did load when one fails", () => {
    // A missing shard should narrow the results, not break the box.
    vi.stubGlobal("fetch", (url: string) =>
      url.includes("fort-wayne")
        ? Promise.reject(new Error("network down"))
        : Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve([doc({ title: "ok" })]),
          } as Response),
    );
    silenceErrors();
    const load = makeIndexLoader("/search-index.json", SHARDS, "fort-wayne");
    return load("site").then((docs) => expect(docs.map((d) => d.title)).toEqual(["ok"]));
  });

  it("treats a non-2xx shard as absent rather than parsing the error page", () => {
    // `fetch` doesn't reject on 404 — the body would be the 404 page's HTML, and `.json()` would
    // throw somewhere less legible. The likely cause of a 404 here is a `_redirects` rule
    // shadowing the shard, which is why the status is checked and logged rather than inferred.
    vi.stubGlobal("fetch", (url: string) =>
      url.includes("fort-wayne")
        ? Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve([]) } as Response)
        : Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve([doc({ title: "ok" })]),
          } as Response),
    );
    silenceErrors();
    const load = makeIndexLoader("/search-index.json", SHARDS, "fort-wayne");
    return load("site").then((docs) => {
      expect(docs.map((d) => d.title)).toEqual(["ok"]);
      expect(quiet).toHaveBeenCalled();
    });
  });

  it("with no current site, site scope still loads the network shard alone", () => {
    // Standing off a site (the wiki, /about) there is nothing to narrow to.
    const seen = stubFetch();
    const load = makeIndexLoader("/search-index.json", SHARDS, null);
    return load("site").then(() => expect(seen).toEqual(["/search-index.json"]));
  });
});

describe("searchEngine.renderAskHandoff — the cross-reference (#1890)", () => {
  it("carries the query to /ask, base-prefixed and escaped", () => {
    const html = renderAskHandoff('deed "smith" & co', "/app", 0);
    expect(html).toContain('href="/app/ask?q=deed%20%22smith%22%20%26%20co"');
    expect(html).toContain("&quot;smith&quot; &amp; co"); // shown back to the reader, escaped
  });

  it("says something different when there were no hits at all", () => {
    expect(renderAskHandoff("x", "", 0)).toContain("No page title or record field matches");
    expect(renderAskHandoff("x", "", 2)).toContain("Not what you meant?");
  });
});
