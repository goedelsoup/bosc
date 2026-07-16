// POST /api/ask — the public "Ask the corpus" endpoint (Epic #207).
//
// A Cloudflare Pages Function colocated with the static site, so the /ask page posts
// same-origin (mirrors api/submit.ts). Workers runtime, Web platform globals only, no
// Node/Python, no SDK deps — the Anthropic Messages API is called directly over fetch.
// See docs/ask-api.md for the contract and the grounding/refusal policy.
//
// Flow: kill switch → parse + length-cap → per-IP rate limit → daily budget guard →
// verify Turnstile → retrieve top-K from the build-time ask-index → if nothing relevant,
// refuse deterministically (no model call) → else assemble a grounding prompt and ask the
// model to answer ONLY from those sources, citing each claim → return the answer +
// structured citations, then record the spend.

import {
  type AskResult,
  assemblePrompt,
  candidateCitations,
  extractCitations,
  isRefusal,
  normalizeQuestion,
  REFUSAL,
} from "./_lib/ask";
import { AnthropicError, type AnthropicUsage, createMessage } from "./_lib/anthropic";
import { streamMessage } from "./_lib/anthropicStream";
import { loadAskIndex } from "./_lib/askIndexLoad";
import { validateAsk } from "./_lib/askSchema";
import { addUsage, costDollars, DEFAULT_DAILY_TOKEN_BUDGET, isOverBudget } from "./_lib/budget";
import { intEnv } from "./_lib/env";
import { hybridSearch } from "./_lib/hybridRetrieve";
import { json, parseJsonBody, requireEnabled } from "./_lib/http";
import { enforceRateLimit, type KVLike } from "./_lib/ratelimit";
import { type PreparedIndex, prepare } from "./_lib/retrieval";
import { frame } from "./_lib/sse";
import { initTracer } from "./_lib/otel";
import { isPluginAuthorized } from "./_lib/askPluginAuth";
import { verifyTurnstile } from "./_lib/turnstile";

interface Env {
  /** On/kill switch — anything but "true" disables the endpoint (mirror submit). */
  ASK_ENABLED?: string;
  /** Anthropic key (Cloudflare secret). Absent ⇒ the endpoint is misconfigured. */
  ANTHROPIC_API_KEY?: string;
  /** Server-side Turnstile secret (Cloudflare secret). Absent ⇒ misconfigured. */
  TURNSTILE_SECRET_KEY?: string;
  /** Shared Bearer service token for the ChatGPT-plugin bypass of Turnstile (#1578).
   *  Absent ⇒ no bypass (Turnstile stays required for every request). */
  ASK_PLUGIN_TOKEN?: string;
  /** Override the Messages API endpoint (local dev mock). Absent ⇒ api.anthropic.com. */
  ANTHROPIC_API_BASE?: string;
  /** Model id; defaults to the repo default. */
  ASK_MODEL?: string;
  /** Hard answer-length cap (cost guard); default 1024. */
  ASK_MAX_TOKENS?: string;
  /** Retrieval depth; default 6. */
  ASK_TOP_K?: string;
  /** Optional override for the ask-index asset URL (sharded/CDN index). */
  ASK_INDEX_URL?: string;
  /** Optional KV namespace for per-IP rate limiting. */
  ASK_RATE_LIMIT?: KVLike;
  /** Per-IP fixed-window limits (defaults below). */
  ASK_RATE_LIMIT_MAX?: string;
  ASK_RATE_LIMIT_WINDOW_SEC?: string;
  /** Optional KV namespace for the account-wide daily budget counter. Falls back to
   *  ASK_RATE_LIMIT, so the budget can be enforced independently of per-IP limiting (#587). */
  ASK_BUDGET?: KVLike;
  /** Account-wide daily total-token budget — input + output (default 200k). A configured "0" is a hard stop. */
  ASK_DAILY_TOKEN_BUDGET?: string;
  /** Escape hatch: with no budget KV bound the paid endpoint fails closed (#587) unless this
   *  is "true" (local dev / explicit operator opt-in to an uncapped endpoint). */
  ASK_ALLOW_UNCAPPED?: string;
  /** Honeycomb write key for edge OTel (#958). Absent ⇒ tracing no-ops. */
  HONEYCOMB_API_KEY?: string;
  /** Sets deployment.environment on spans (default "prod"). */
  OTEL_ENVIRONMENT?: string;
  /** Answer-cache TTL in seconds (default 3600 = 1 hr; "0" disables the cache). */
  ASK_CACHE_MAX_AGE?: string;
  /** Cloudflare Workers AI binding (#329) — query embedding for hybrid retrieval.
   *  Absent ⇒ BM25-only keyword retrieval (graceful degradation). */
  AI?: { run(model: string, input: { text: string[] }): Promise<{ data: number[][] }> };
  /** Optional override for the ask-embeddings asset URL (e.g. CDN-hosted). */
  ASK_EMBEDDINGS_URL?: string;
}

// A paid endpoint deserves a tighter per-IP window than the tips form.
const DEFAULT_ASK_RATE_LIMIT = { max: 10, windowSec: 3600 };

interface RequestContext {
  request: Request;
  env: Env;
  waitUntil: (promise: Promise<unknown>) => void;
}

const sse = (stream: ReadableStream): Response =>
  new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    },
  });

// Answer-cache (#332): Workers Cache API keyed on the normalized question. Returns null in
// non-Workers environments (Node tests) where `caches` is not defined.
async function getAnswerCache(): Promise<Cache | null> {
  try {
    return typeof caches !== "undefined" ? await caches.open("ask-answers") : null;
  } catch {
    return null;
  }
}

// Synthesize an SSE stream from a cached AskResult so streaming clients get the same
// event shape they'd receive from a live model call (meta → delta → done).
function syntheticCacheStream(cached: AskResult): ReadableStream {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      const send = (event: string, data: unknown): void => controller.enqueue(enc.encode(frame(event, data)));
      // candidates = resolved citations so live [n] rendering works on the single delta
      send("meta", { searched: 0, candidates: cached.citations });
      if (!cached.refused) send("delta", { text: cached.answer });
      send("done", {
        citations: cached.citations,
        refused: cached.refused,
        model: cached.model,
        usage: cached.usage,
      });
      controller.close();
    },
  });
}

const DEFAULT_MODEL = "claude-opus-4-8";
const DEFAULT_MAX_TOKENS = 1024;
const DEFAULT_TOP_K = 6;

// Prepared-index cache: keyed by units identity so it rebuilds only when the cached
// asset does (both live for the isolate's lifetime).
let preparedFor: unknown = null;
let prepared: PreparedIndex | null = null;
function getPrepared(units: Parameters<typeof prepare>[0]): PreparedIndex {
  if (prepared && preparedFor === units) return prepared;
  prepared = prepare(units);
  preparedFor = units;
  return prepared;
}

export const onRequestPost = async (ctx: RequestContext): Promise<Response> => {
  const { request, env, waitUntil } = ctx;
  const otelHandle = initTracer(env);
  const otelSpan = otelHandle?.startSpan("ask.request");

  const disabled = requireEnabled(env.ASK_ENABLED, () =>
    json(503, { error: "the ask endpoint is not enabled" }),
  );
  if (disabled) return disabled;
  if (!env.ANTHROPIC_API_KEY || !env.TURNSTILE_SECRET_KEY)
    return json(500, { error: "endpoint is misconfigured" });
  const apiKey = env.ANTHROPIC_API_KEY; // captured for the stream closure (narrowing is lost there)

  const body = await parseJsonBody(request);
  if (!body.ok) return body.response;

  const parsed = validateAsk(body.value);
  if (!parsed.ok) return json(400, { error: parsed.error });
  const { question, turnstile_token } = parsed.value;
  const wantsStream = (request.headers.get("Accept") ?? "").includes("text/event-stream");

  // Budget counter KV — its own optional binding, falling back to the rate-limit namespace, so
  // the daily cap can be enforced without also enabling per-IP limiting (#587).
  const budgetKv = env.ASK_BUDGET ?? env.ASK_RATE_LIMIT;

  // Fail-closed: a pure local check — no KV + no explicit uncapped opt-in means the paid
  // endpoint isn't configured for production spend. Refuse before any external call (#587).
  if (!budgetKv && env.ASK_ALLOW_UNCAPPED !== "true") {
    console.error("ask: no budget KV bound and ASK_ALLOW_UNCAPPED!=true — refusing (fail-closed)");
    return json(503, { error: "the ask endpoint is temporarily unavailable" });
  }

  const remoteip = request.headers.get("CF-Connecting-IP") ?? undefined;
  const nowMs = Date.now();

  // Per-IP rate limit applies to all requests including cache hits — prevents cache DoS.
  // Soft + fail-open on KV error (Turnstile is the primary gate).
  if (env.ASK_RATE_LIMIT && remoteip) {
    const blocked = await enforceRateLimit(
      env.ASK_RATE_LIMIT,
      remoteip,
      Math.floor(nowMs / 1000),
      {
        max: intEnv(env.ASK_RATE_LIMIT_MAX, DEFAULT_ASK_RATE_LIMIT.max),
        windowSec: Math.max(60, intEnv(env.ASK_RATE_LIMIT_WINDOW_SEC, DEFAULT_ASK_RATE_LIMIT.windowSec)),
      },
      "too many questions — please try again later",
    );
    if (blocked) return blocked;
  }

  // Human-verification gate — applies to all requests including cache hits (the token is
  // single-use either way). A ChatGPT plugin / GPT Action can't solve Turnstile, so a request
  // bearing a valid `Authorization: Bearer <ASK_PLUGIN_TOKEN>` stands in for the challenge
  // (#1578); the per-IP rate limit + daily budget guards still apply to that traffic.
  if (!isPluginAuthorized(request, env)) {
    if (!turnstile_token)
      return json(403, { error: "verification required — please complete the challenge" });
    const human = await verifyTurnstile(turnstile_token, env.TURNSTILE_SECRET_KEY, remoteip);
    if (!human) return json(403, { error: "verification failed — please retry the challenge" });
  }

  // Answer cache (#332): fail-closed, rate-limit, and Turnstile have already passed; skip the
  // budget guard and model call for cache hits (no token spend). ASK_CACHE_MAX_AGE=0 disables.
  const cacheMaxAge = Math.max(0, intEnv(env.ASK_CACHE_MAX_AGE, 3600));
  const answerCache = cacheMaxAge > 0 ? await getAnswerCache() : null;
  const cacheKeyUrl = `https://ask-cache.internal/v1/${encodeURIComponent(normalizeQuestion(question))}`;
  if (answerCache) {
    try {
      const hit = await answerCache.match(new Request(cacheKeyUrl));
      if (hit) {
        const cached = (await hit.json()) as AskResult;
        return wantsStream ? sse(syntheticCacheStream(cached)) : json(200, cached);
      }
    } catch {
      // Cache read error — fall through to the normal path.
    }
  }

  const budgetLimit = Math.max(0, intEnv(env.ASK_DAILY_TOKEN_BUDGET, DEFAULT_DAILY_TOKEN_BUDGET));
  if (budgetKv && (await isOverBudget(budgetKv, nowMs, budgetLimit)))
    return json(503, { error: "the ask endpoint has reached today's budget — please try again tomorrow" });

  // Retrieve grounding context — BM25 baseline, upgraded to hybrid when the AI binding
  // and precomputed embeddings are both available (#329). Degrades gracefully to BM25-only.
  let units: Awaited<ReturnType<typeof loadAskIndex>>;
  try {
    units = await loadAskIndex(request.url, env.ASK_INDEX_URL);
  } catch (e) {
    console.error("ask-index load failed:", e);
    return json(500, { error: "the corpus index is unavailable" });
  }
  const k = Math.max(1, intEnv(env.ASK_TOP_K, DEFAULT_TOP_K));
  const hits = await hybridSearch(getPrepared(units), question, k, env, request.url);

  const model = env.ASK_MODEL || DEFAULT_MODEL;
  const maxTokens = Math.max(256, intEnv(env.ASK_MAX_TOKENS, DEFAULT_MAX_TOKENS));

  // Record spend against the daily budget + emit structured telemetry for observability.
  // outcome: "no_hits" = refused before any model call; "refused" = model refusal; "answered" = normal.
  let callT0 = 0;
  const record = async (
    outcome: "answered" | "refused" | "no_hits",
    usage?: AnthropicUsage,
  ): Promise<void> => {
    const latencyMs = callT0 > 0 ? Date.now() - callT0 : undefined;
    const cost = usage != null ? costDollars(usage, model) : null;
    const entry: Record<string, unknown> = { endpoint: "ask", outcome, model, hits: hits.length };
    if (usage != null) {
      entry.input_tokens = usage.input_tokens;
      entry.output_tokens = usage.output_tokens;
    }
    if (cost != null) entry.cost_usd = cost;
    else if (usage != null) entry.pricing_unknown = true;
    if (latencyMs != null) entry.latency_ms = latencyMs;
    console.log(JSON.stringify(entry));
    // OTel span attributes mirror the console.log entry (#958)
    otelSpan?.setAttribute("ask.outcome", outcome);
    otelSpan?.setAttribute("retrieval.hits", hits.length);
    otelSpan?.setAttribute("llm.model", model);
    if (usage != null) {
      otelSpan?.setAttribute("llm.usage.input_tokens", usage.input_tokens);
      otelSpan?.setAttribute("llm.usage.output_tokens", usage.output_tokens);
    }
    if (cost != null) otelSpan?.setAttribute("ask.cost_usd", cost);
    if (latencyMs != null) otelSpan?.setAttribute("ask.latency_ms", latencyMs);
    otelSpan?.end();
    if (usage != null && budgetKv) await addUsage(budgetKv, nowMs, usage);
  };

  // Nothing relevant retrieved ⇒ refuse deterministically, before spending a model call.
  if (hits.length === 0) {
    await record("no_hits");
    if (otelHandle) waitUntil(otelHandle.flush());
    if (wantsStream) {
      return sse(
        new ReadableStream({
          start(controller) {
            const enc = new TextEncoder();
            // Emit `meta` first on every stream so the client has one code path (#331).
            controller.enqueue(enc.encode(frame("meta", { searched: 0, candidates: [] })));
            controller.enqueue(enc.encode(frame("delta", { text: REFUSAL })));
            controller.enqueue(enc.encode(frame("done", { citations: [], refused: true, model })));
            controller.close();
          },
        }),
      );
    }
    return json(200, { answer: REFUSAL, citations: [], refused: true, model } satisfies AskResult);
  }

  const { system, user } = assemblePrompt(question, hits);
  const messages = [{ role: "user" as const, content: user }];

  // Streaming path (#214): relay Anthropic token deltas as SSE, reconcile citations at
  // end-of-stream. Abuse/cost guards above already ran; spend is recorded once usage lands.
  if (wantsStream) {
    const enc = new TextEncoder();
    // Deferred promise so the OTel flush fires after the span ends inside the stream.
    let resolveStreamDone: (() => void) | undefined;
    const streamDone = otelHandle
      ? new Promise<void>((r) => {
          resolveStreamDone = r;
        })
      : Promise.resolve();
    const stream = new ReadableStream({
      async start(controller) {
        const send = (event: string, data: unknown): void =>
          controller.enqueue(enc.encode(frame(event, data)));
        // Pre-answer: tell the client how many records ground this answer and ship the
        // candidate citations so it can resolve `[n]` markers as tokens stream in (#331).
        send("meta", { searched: hits.length, candidates: candidateCitations(hits) });
        let full = "";
        let inTok: number | undefined;
        let outTok: number | undefined;
        try {
          callT0 = Date.now();
          for await (const chunk of streamMessage({
            apiKey,
            model,
            system,
            messages,
            maxTokens,
            apiUrl: env.ANTHROPIC_API_BASE,
          })) {
            if (chunk.text) {
              full += chunk.text;
              send("delta", { text: chunk.text });
            }
            if (chunk.inputTokens != null) inTok = chunk.inputTokens;
            if (chunk.outputTokens != null) outTok = chunk.outputTokens;
          }
        } catch (e) {
          console.error("ask stream failed:", e);
          otelSpan?.setStatus("error");
          otelSpan?.end();
          resolveStreamDone?.();
          send("error", { error: "could not generate an answer — please try again later" });
          controller.close();
          return;
        }
        const usage =
          inTok != null && outTok != null ? { input_tokens: inTok, output_tokens: outTok } : undefined;
        const refused = isRefusal(full);
        const citations = refused ? [] : extractCitations(full, hits);
        await record(refused ? "refused" : "answered", usage);
        resolveStreamDone?.();
        send("done", { citations, refused, model, usage });
        if (answerCache && !refused) {
          const result: AskResult = { answer: full, citations, refused, model, usage };
          const toCache = new Response(JSON.stringify(result), {
            headers: {
              "content-type": "application/json",
              "cache-control": `public, max-age=${cacheMaxAge}`,
            },
          });
          waitUntil(answerCache.put(new Request(cacheKeyUrl), toCache));
        }
        controller.close();
      },
    });
    if (otelHandle) waitUntil(streamDone.then(() => otelHandle.flush()));
    return sse(stream);
  }

  // Non-streaming path — the JSON contract for tools / the eval / no-SSE clients.
  let text: string;
  let usage: AskResult["usage"];
  try {
    callT0 = Date.now();
    const res = await createMessage({
      apiKey,
      model,
      system,
      messages,
      maxTokens,
      apiUrl: env.ANTHROPIC_API_BASE,
    });
    text = res.text;
    usage = res.usage;
  } catch (e) {
    const status = e instanceof AnthropicError ? e.status : 0;
    console.error("ask model call failed:", status, e);
    otelSpan?.setStatus("error");
    otelSpan?.end();
    if (otelHandle) waitUntil(otelHandle.flush());
    return json(502, { error: "could not generate an answer — please try again later" });
  }
  const refused = isRefusal(text);
  const citations = refused ? [] : extractCitations(text, hits);
  await record(refused ? "refused" : "answered", usage);
  if (otelHandle) waitUntil(otelHandle.flush());
  const result: AskResult = { answer: text, citations, refused, model, usage };
  if (answerCache && !refused) {
    const toCache = new Response(JSON.stringify(result), {
      headers: { "content-type": "application/json", "cache-control": `public, max-age=${cacheMaxAge}` },
    });
    waitUntil(answerCache.put(new Request(cacheKeyUrl), toCache));
  }
  return json(200, result satisfies AskResult);
};
