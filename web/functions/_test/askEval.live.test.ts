// Faithfulness eval — live tier (#215). Calls the real model to assert the grounding/refusal
// behavior the fixture tier can't prove — grounded answers cite, and hallucination-bait that
// DOES retrieve context is still refused.
//
//   ASK_EVAL_LIVE=1 ANTHROPIC_API_KEY=sk-... npm test -- askEval.live  (optionally ASK_EVAL_MODEL=...)
//
// The opt-in is ASK_EVAL_LIVE, NOT the mere presence of a key (#2026). Gating on the key alone
// looked equivalent — absent in CI, so CI stayed cheap and offline — but a key lives in `.env` on
// every working machine, so the suite auto-armed inside `mise run //web:check`. That charged the
// developer's account on every gate run and, worse, asserted determinism it does not have: 3-5 of
// these 11 assertions fail on any given run because `allClaimsCited` judges free-form prose. The
// resulting red aborted the gate before the build and the three post-build guards. An eval whose
// pass/fail is a model sample belongs behind a deliberate flag, never in a blocking gate.

import { describe, expect, it } from "vitest";
import { assemblePrompt, extractCitations, isRefusal } from "@watermark/functions/api/_lib/ask";
import { createMessage } from "@watermark/functions/api/_lib/anthropic";
import { retrieve } from "@watermark/functions/api/_lib/retrieval";
import { CORPUS, HALLUCINATION_BAIT, IN_CORPUS } from "./askEval.fixtures";

const apiKey = process.env.ANTHROPIC_API_KEY;
/** Both are required: the deliberate flag AND a key to spend. */
const live = process.env.ASK_EVAL_LIVE === "1" && Boolean(apiKey);
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

describe.skipIf(!live)("live faithfulness eval", () => {
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
