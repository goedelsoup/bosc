// Faithfulness eval — fixture tier (#215). Deterministic, no model call, runs in CI.
// Guards the two properties that keep a litigation-evidence Q&A honest: answers are
// grounded in retrieval, and the record's silence becomes a refusal (not a guess).

import { describe, expect, it } from "vitest";
import { assemblePrompt, extractCitations, isRefusal, REFUSAL } from "@watermark/functions/api/_lib/ask";
import { retrieve } from "@watermark/functions/api/_lib/retrieval";
import { CORPUS, IN_CORPUS, OUT_OF_CORPUS } from "./askEval.fixtures";

describe("grounding — in-corpus questions surface the right source", () => {
  for (const { question, expectFeeds } of IN_CORPUS) {
    it(question, () => {
      const hits = retrieve(CORPUS, question, 6);
      expect(hits.length).toBeGreaterThan(0);
      expect(expectFeeds).toContain(hits[0].unit.feed);
    });
  }
});

describe("refusal — out-of-corpus questions retrieve nothing (→ deterministic refusal)", () => {
  for (const question of OUT_OF_CORPUS) {
    it(question, () => {
      // Empty retrieval is exactly the route's no-model-call refusal branch.
      expect(retrieve(CORPUS, question, 6)).toEqual([]);
    });
  }
});

describe("prompt contract", () => {
  it("instructs strict grounding, citation, and the canonical refusal", () => {
    const { system, user } = assemblePrompt(
      IN_CORPUS[0].question,
      retrieve(CORPUS, IN_CORPUS[0].question, 3),
    );
    expect(system).toContain(REFUSAL);
    expect(system).toMatch(/ONLY the provided sources/i);
    expect(system).toMatch(/cite every factual claim/i);
    // The numbered, fenced sources the model must cite by are present in the user turn.
    expect(user).toContain('<source id="1">');
  });
});

describe("citation grounding — markers resolve to the retrieved sources", () => {
  it("a cited [n] maps back to a real retrieved unit", () => {
    const hits = retrieve(CORPUS, "What do the roundabout cost estimates total?", 6);
    const cites = extractCitations("The six estimates are summarized [1].", hits);
    expect(cites).toHaveLength(1);
    expect(hits.some((h) => h.unit.id === cites[0].id)).toBe(true);
  });

  it("isRefusal recognizes the canonical refusal (the empty-retrieval answer)", () => {
    expect(isRefusal(REFUSAL)).toBe(true);
  });
});
