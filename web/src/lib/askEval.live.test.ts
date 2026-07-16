// Faithfulness eval — live tier (#215). GATED on ANTHROPIC_API_KEY: skipped (so CI stays
// cheap + offline) unless a key is present, then it calls the real model to assert the
// grounding/refusal behavior the fixture tier can't prove — grounded answers cite, and
// hallucination-bait that DOES retrieve context is still refused.
//
//   ANTHROPIC_API_KEY=sk-... npm test -- askEval.live   (optionally ASK_EVAL_MODEL=...)

import { describe, expect, it } from "vitest";
import { assemblePrompt, extractCitations, isRefusal } from "@watermark/functions/api/_lib/ask";
import { createMessage } from "@watermark/functions/api/_lib/anthropic";
import { retrieve } from "@watermark/functions/api/_lib/retrieval";
import { CORPUS, HALLUCINATION_BAIT, IN_CORPUS } from "./askEval.fixtures";

const apiKey = process.env.ANTHROPIC_API_KEY;
const model = process.env.ASK_EVAL_MODEL || "claude-opus-4-8";
const TIMEOUT = 60_000;

/**
 * True when every substantive sentence in the answer carries at least one `[n]` citation.
 * The system prompt requires "cite every factual claim" — this checks the density contract
 * is upheld, not just that at least one citation appears somewhere in the answer.
 * Sentences with ≤ 5 words are assumed connective/transitional and are excluded.
 */
function allClaimsCited(text: string): boolean {
  const sentences = text.split(/(?<=[.!?])\s+/);
  return sentences.every((s) => {
    const words = s.trim().split(/\s+/).length;
    return words <= 5 || /\[\d+\]/.test(s);
  });
}

async function answer(question: string): Promise<{ text: string; hits: ReturnType<typeof retrieve> }> {
  const hits = retrieve(CORPUS, question, 6);
  const { system, user } = assemblePrompt(question, hits);
  const res = await createMessage({
    apiKey: apiKey as string,
    model,
    system,
    messages: [{ role: "user", content: user }],
    maxTokens: 512,
  });
  return { text: res.text, hits };
}

describe.skipIf(!apiKey)("live faithfulness eval", () => {
  for (const { question } of IN_CORPUS) {
    it(
      `answers + cites: ${question}`,
      async () => {
        const { text, hits } = await answer(question);
        expect(isRefusal(text)).toBe(false);
        const cites = extractCitations(text, hits);
        expect(cites.length).toBeGreaterThan(0);
        // Every substantive sentence must carry a citation — "cite every factual claim"
        expect(allClaimsCited(text)).toBe(true);
      },
      TIMEOUT,
    );
  }

  for (const question of HALLUCINATION_BAIT) {
    it(
      `refuses bait: ${question}`,
      async () => {
        const { text, hits } = await answer(question);
        // The bait shares vocabulary, so retrieval is non-empty — the refusal must come
        // from the model honoring the grounding rules, not from the empty-retrieval shortcut.
        expect(hits.length).toBeGreaterThan(0);
        expect(isRefusal(text)).toBe(true);
      },
      TIMEOUT,
    );
  }
});
