import { describe, expect, it } from "vitest";
import { agencyMatches, countyKey, facetKey, permitKey, permitMatches, projectKey } from "./askFacets";

// The matching semantics of the #1691 search facets. These are shared by the build-time producer
// (askIndex) and the query-time kernel (retrieval.applyCorpusFilters), so what's asserted here is
// the contract between them — not an implementation detail of either.
describe("facetKey", () => {
  it("collapses case, punctuation and spacing, which are presentation not identity", () => {
    expect(facetKey("Ohio EPA")).toBe("ohio epa");
    expect(facetKey("ohio  epa")).toBe("ohio epa");
    expect(facetKey("Amazon.com Services LLC")).toBe("amazon com services llc");
    expect(facetKey("AMAZON COM SERVICES")).toBe("amazon com services");
  });

  it("is empty for a value with nothing to compare", () => {
    expect(facetKey("  —  ")).toBe("");
  });
});

describe("countyKey", () => {
  it("collapses every way the network writes one county", () => {
    // The profile's own form, the caller's shorthand, and a peer that carries no state suffix.
    expect(countyKey("Allen County, OH")).toBe("allen");
    expect(countyKey("Allen County")).toBe("allen");
    expect(countyKey("allen")).toBe("allen");
    expect(countyKey("Richland County")).toBe("richland");
  });

  it("keeps a multi-word county name intact", () => {
    expect(countyKey("Van Wert County, OH")).toBe("van wert");
  });
});

describe("permitKey / permitMatches", () => {
  it("ignores the separators an agency happens to print an id with", () => {
    expect(permitKey("2PH00006*LD")).toBe("2PH00006LD");
    expect(permitKey("dsw-401252260/w")).toBe("DSW401252260W");
  });

  it("matches a base permit number to every modification filed under it", () => {
    // The motivating case: Ohio issues one permit and prints each action with its own suffix.
    expect(permitMatches(["2PH00006*LD"], "2PH00006")).toBe(true);
    expect(permitMatches(["2PH00006*MD"], "2PH00006")).toBe(true);
  });

  it("does not widen a specific instrument back to the base", () => {
    expect(permitMatches(["2PH00006"], "2PH00006*LD")).toBe(false);
  });

  it("matches any of a unit's ids, so a record is findable by either identifier", () => {
    expect(permitMatches(["2PH00006*LD", "OH0037338"], "OH0037338")).toBe(true);
  });

  it("does not confuse two permits that merely share a prefix boundary-free", () => {
    expect(permitMatches(["OH0037338"], "OH0037339")).toBe(false);
  });

  it("matches nothing on an empty query — a set facet must constrain", () => {
    expect(permitMatches(["2PH00006*LD"], "  ")).toBe(false);
  });
});

describe("agencyMatches", () => {
  it("reaches a division from the parent agency's name", () => {
    expect(agencyMatches("Ohio EPA, Division of Surface Water", "Ohio EPA")).toBe(true);
    expect(agencyMatches("Ohio EPA (DAPC; Office of the Supervising Attorney)", "ohio epa")).toBe(true);
  });

  it("is directional — a narrower query never matches a broader record", () => {
    expect(agencyMatches("Ohio EPA", "Ohio EPA, Division of Surface Water")).toBe(false);
  });

  it("separates distinct agencies", () => {
    expect(agencyMatches("U.S. Army Corps of Engineers", "Ohio EPA")).toBe(false);
    expect(agencyMatches("U.S. Army Corps of Engineers", "army corps")).toBe(true);
  });

  it("matches nothing on an empty query", () => {
    expect(agencyMatches("Ohio EPA", "")).toBe(false);
  });
});

describe("projectKey", () => {
  it("writes a stated project name and a facility key in one vocabulary", () => {
    expect(projectKey("Project BOSC")).toBe("project-bosc");
    expect(projectKey("Project Bosc")).toBe("project-bosc");
    expect(projectKey("project-bosc")).toBe("project-bosc");
    expect(projectKey("Van Wert Mega Site")).toBe("van-wert-mega-site");
  });
});
