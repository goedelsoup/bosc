// POST /api/mcp — MCP Streamable HTTP transport endpoint (#911).
//
// Implements the MCP Streamable HTTP transport (spec 2025-03-26):
// https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/#streamable-http
//
// JSON-RPC 2.0 dispatch over a single POST endpoint. Synchronous methods
// (initialize, tools/list, resources/list) return application/json directly;
// tools/call returns text/event-stream so implementations can stream results.
// Sessions are stored in MCP_SESSIONS KV (Mcp-Session-Id header round-trip).
//
// Flow: kill switch → auth (#916) → per-IP rate limit → budget guard (#912)
//       → parse body → session lookup/create → dispatch → return JSON or SSE.

import { dispatch, RPC } from "./_lib/mcpDispatch";
import { json, parseJsonBody } from "./_lib/http";
import { initTracer } from "./_lib/otel";
import { enforceRateLimit, type KVLike } from "./_lib/ratelimit";
import { frame } from "./_lib/sse";
import { getSession, newSessionId, putSession } from "./_lib/mcpSession";
import { verifyToken, type McpAuthEnv } from "./_lib/mcpAuth";
import {
  DEFAULT_KEY_DAILY,
  DEFAULT_PUBLIC_DAILY,
  addBudgetUsage,
  isOverBudget,
  keyedBudgetKey,
  publicBudgetKey,
} from "./_lib/mcpBudget";
import { estimateTokens } from "./_lib/mcpGovern";

interface Env extends McpAuthEnv {
  /** Kill switch — anything but "true" disables the endpoint. */
  MCP_ENABLED?: string;
  /** KV namespace for session storage. */
  MCP_SESSIONS?: KVLike;
  /** Optional KV namespace for per-IP rate limiting. */
  MCP_RATE_LIMIT?: KVLike;
  MCP_RATE_LIMIT_MAX?: string;
  MCP_RATE_LIMIT_WINDOW_SEC?: string;
  /** KV namespace for the daily output-token budget (#912). */
  MCP_BUDGET?: KVLike;
  /** Kill switch for budget enforcement. Default off (no enforcement until wired). */
  MCP_BUDGET_ENABLED?: string;
  /** Shared public-tier daily cap (output tokens). */
  MCP_BUDGET_PUBLIC_DAILY?: string;
  /** Per-key (cognito) daily cap (output tokens). */
  MCP_BUDGET_KEY_DAILY?: string;
  /** Bypass all budget guards for local dev (mirrors ASK_ALLOW_UNCAPPED). */
  MCP_ALLOW_UNCAPPED?: string;
  /** Honeycomb write key for edge OTel (#958). Absent ⇒ tracing no-ops. */
  HONEYCOMB_API_KEY?: string;
  /** Sets deployment.environment on spans (default "prod"). */
  OTEL_ENVIRONMENT?: string;
  /** Cloudflare Workers AI binding (#1586) — query embedding for hybrid search_corpus.
   *  Absent ⇒ BM25-only keyword retrieval (graceful degradation, mirrors /api/ask). */
  AI?: { run(model: string, input: { text: string[] }): Promise<{ data: number[][] }> };
  /** Optional override for the ask-embeddings asset URL (e.g. CDN-hosted). */
  ASK_EMBEDDINGS_URL?: string;
}

const DEFAULT_MCP_RATE_LIMIT = { max: 60, windowSec: 60 }; // 60 req/min per IP

function sseResponse(body: string, headers?: Record<string, string>): Response {
  return new Response(body, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      ...headers,
    },
  });
}

function intEnv(val: string | undefined, fallback: number): number {
  const n = Number(val);
  return Number.isFinite(n) ? n : fallback;
}

interface RequestContext {
  request: Request;
  env: Env;
  waitUntil: (promise: Promise<unknown>) => void;
}

export async function onRequestPost({ request, env, waitUntil }: RequestContext): Promise<Response> {
  // Kill switch
  if (env.MCP_ENABLED !== "true") {
    return json(503, {
      jsonrpc: "2.0",
      id: null,
      error: { code: RPC.INTERNAL_ERROR, message: "MCP endpoint is not enabled" },
    });
  }

  // Auth (#916) — public passthrough or Bearer key verification
  const authResult = await verifyToken(request, env);
  if ("error" in authResult) {
    return json(200, {
      jsonrpc: "2.0",
      id: null,
      error: { code: RPC.INVALID_REQUEST, message: "authentication failed", data: "auth" },
    });
  }

  // Per-IP rate limit
  if (env.MCP_RATE_LIMIT) {
    const ip =
      request.headers.get("cf-connecting-ip") ??
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      "unknown";
    const cfg = {
      max: intEnv(env.MCP_RATE_LIMIT_MAX, DEFAULT_MCP_RATE_LIMIT.max),
      windowSec: intEnv(env.MCP_RATE_LIMIT_WINDOW_SEC, DEFAULT_MCP_RATE_LIMIT.windowSec),
    };
    const denied = await enforceRateLimit(
      env.MCP_RATE_LIMIT,
      ip,
      Math.floor(Date.now() / 1000),
      cfg,
      "rate limit exceeded",
    );
    if (denied) return denied;
  }

  // Budget guard (#912) — only active when MCP_BUDGET_ENABLED="true". The resolved KV +
  // per-day key are hoisted so the post-dispatch debit (#1581) reuses the same tier/key.
  const nowMs = Date.now();
  const budgetEnabled = env.MCP_BUDGET_ENABLED === "true" && env.MCP_ALLOW_UNCAPPED !== "true";
  let budgetKv: KVLike | undefined;
  let budgetKey = "";
  if (budgetEnabled) {
    budgetKv = env.MCP_BUDGET;
    if (!budgetKv) {
      console.error("mcp: MCP_BUDGET_ENABLED=true but no MCP_BUDGET KV bound — refusing (fail-closed)");
      return json(503, {
        jsonrpc: "2.0",
        id: null,
        error: { code: RPC.INTERNAL_ERROR, message: "budget store not configured" },
      });
    }
    budgetKey =
      authResult.tier === "cognito" ? keyedBudgetKey(authResult.keyHash, nowMs) : publicBudgetKey(nowMs);
    const limit =
      authResult.tier === "cognito"
        ? intEnv(env.MCP_BUDGET_KEY_DAILY, DEFAULT_KEY_DAILY)
        : intEnv(env.MCP_BUDGET_PUBLIC_DAILY, DEFAULT_PUBLIC_DAILY);
    if (await isOverBudget(budgetKv, budgetKey, limit)) {
      return json(200, {
        jsonrpc: "2.0",
        id: null,
        error: {
          code: RPC.INTERNAL_ERROR,
          message: "daily budget exceeded — try again tomorrow",
          data: "budget_exceeded",
        },
      });
    }
  }

  // Parse JSON body
  const parsed = await parseJsonBody(request);
  if (!parsed.ok) {
    return json(400, {
      jsonrpc: "2.0",
      id: null,
      error: { code: RPC.PARSE_ERROR, message: "invalid JSON" },
    });
  }

  // Session management
  const incomingSessionId = request.headers.get("mcp-session-id");
  let sessionId: string;
  const body = parsed.value as Record<string, unknown>;
  const isInitialize = body.method === "initialize";

  if (isInitialize) {
    sessionId = newSessionId();
  } else if (incomingSessionId) {
    if (env.MCP_SESSIONS) {
      const session = await getSession(env.MCP_SESSIONS, incomingSessionId);
      if (!session) {
        return json(404, {
          jsonrpc: "2.0",
          id: body.id ?? null,
          error: { code: RPC.INVALID_REQUEST, message: "unknown or expired session" },
        });
      }
    }
    sessionId = incomingSessionId;
  } else {
    return json(400, {
      jsonrpc: "2.0",
      id: body.id ?? null,
      error: {
        code: RPC.INVALID_REQUEST,
        message: "Mcp-Session-Id header required (call initialize first)",
      },
    });
  }

  // Dispatch — instrument with OTel spans (#958)
  const otelHandle = initTracer(env);
  const rpcSpan = otelHandle?.startSpan("mcp.rpc");
  rpcSpan?.setAttribute("rpc.method", String(body.method ?? "unknown"));
  rpcSpan?.setAttribute("mcp.session", sessionId);

  let rpcResponse: Awaited<ReturnType<typeof dispatch>>;
  if (body.method === "tools/call") {
    const toolName = String((body.params as Record<string, unknown> | undefined)?.name ?? "unknown");
    const toolSpan = otelHandle?.startSpan("mcp.tool", rpcSpan);
    const t0 = Date.now();
    rpcResponse = await dispatch(parsed.value, request.url, env);
    toolSpan?.setAttribute("tool.name", toolName);
    toolSpan?.setAttribute("tool.latency_ms", Date.now() - t0);
    toolSpan?.end();
  } else {
    rpcResponse = await dispatch(parsed.value, request.url, env);
  }

  // Persist the session after a successful initialize
  if (isInitialize && env.MCP_SESSIONS && !rpcResponse.error) {
    await putSession(env.MCP_SESSIONS, {
      id: sessionId,
      protocol: "2025-03-26",
      created: Date.now(),
    });
  }

  const sessionHeaders: Record<string, string> = { "mcp-session-id": sessionId };

  let response: Response;

  // notifications/initialized: 202 No Content (no body needed)
  if (body.method === "notifications/initialized") {
    response = new Response(null, { status: 202, headers: sessionHeaders });
  } else if (body.method === "tools/call") {
    // tools/call: SSE stream so implementations can stream results.
    const eventData = frame("message", rpcResponse);
    // Debit the daily budget by the response's output-token cost (#1581). The corpus text
    // we inject into the caller's context is the spend these tools govern — estimated from
    // the serialized frame so the debit tracks exactly what leaves the endpoint. Errors
    // don't debit (no corpus was returned). Best-effort via waitUntil; fails open.
    if (budgetEnabled && budgetKv && !rpcResponse.error) {
      waitUntil(addBudgetUsage(budgetKv, budgetKey, estimateTokens(eventData)));
    }
    response = sseResponse(eventData, sessionHeaders);
  } else {
    // All other methods: direct JSON
    response = json(200, rpcResponse, sessionHeaders);
  }

  rpcSpan?.end();
  if (otelHandle) waitUntil(otelHandle.flush());
  return response;
}
