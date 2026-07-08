// Streaming variant of the Anthropic Messages client (#214) — Web globals only, no SDK.
// Calls the Messages API with `stream: true`, parses the upstream SSE, and yields plain
// text deltas + final usage so the route can relay them as our own SSE protocol. The
// event→delta mapping is a pure function (`mapAnthropicEvent`), unit-tested.
// https://docs.anthropic.com/en/api/messages-streaming

import { AnthropicError, API_URL, API_VERSION, type AnthropicUsage, type MessageRequest } from "./anthropic";
import { isTimeoutError } from "./http";
import { drainSse, type SseEvent } from "./sse";

/** Idle deadline between stream chunks (ms). A stalled upstream aborts rather than holding
 *  the Worker + the client's SSE connection open indefinitely (#590). */
const STREAM_IDLE_TIMEOUT_MS = 30_000;

/** A normalized chunk from the Anthropic stream. */
export interface StreamChunk {
  /** Incremental answer text (a `text_delta`). */
  text?: string;
  /** Token counts, accumulated across `message_start` + `message_delta`. */
  inputTokens?: number;
  outputTokens?: number;
}

/** Map one upstream SSE event to a normalized chunk (or null to ignore it). Pure. */
export function mapAnthropicEvent(ev: SseEvent): StreamChunk | null {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(ev.data) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (ev.event) {
    case "content_block_delta": {
      const delta = payload.delta as { type?: string; text?: string } | undefined;
      return delta?.type === "text_delta" && typeof delta.text === "string" ? { text: delta.text } : null;
    }
    case "message_start": {
      const usage = (payload.message as { usage?: AnthropicUsage } | undefined)?.usage;
      return usage ? { inputTokens: usage.input_tokens } : null;
    }
    case "message_delta": {
      const usage = payload.usage as { output_tokens?: number } | undefined;
      return usage?.output_tokens != null ? { outputTokens: usage.output_tokens } : null;
    }
    default:
      return null;
  }
}

/** Stream a grounded answer, yielding normalized chunks. Throws AnthropicError on a bad
 *  start or a stalled stream (no chunk within `idleMs` → a clean 504). */
export async function* streamMessage(
  req: MessageRequest,
  idleMs: number = STREAM_IDLE_TIMEOUT_MS,
): AsyncGenerator<StreamChunk> {
  // One controller guards the whole stream: an idle timer (re-armed on every chunk) aborts
  // both the initial fetch and a mid-stream stall, so a hung upstream can't pin us open.
  const controller = new AbortController();
  let idle = setTimeout(() => controller.abort(), idleMs);
  const rearm = (): void => {
    clearTimeout(idle);
    idle = setTimeout(() => controller.abort(), idleMs);
  };

  let res: Response;
  try {
    res = await fetch(req.apiUrl || API_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": req.apiKey,
        "anthropic-version": API_VERSION,
        accept: "text/event-stream",
      },
      body: JSON.stringify({
        model: req.model,
        max_tokens: req.maxTokens,
        // Only include `temperature` when a caller set one — newer models reject it (see MessageRequest).
        ...(req.temperature !== undefined ? { temperature: req.temperature } : {}),
        system: req.system,
        messages: req.messages,
        stream: true,
      }),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(idle);
    if (isTimeoutError(e)) throw new AnthropicError("Anthropic stream timed out", 504);
    throw e;
  }
  if (!res.ok || !res.body) {
    clearTimeout(idle);
    const detail = await res.text().catch(() => "");
    throw new AnthropicError(detail || `Anthropic API error ${res.status}`, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch (e) {
        if (isTimeoutError(e)) throw new AnthropicError("Anthropic stream stalled", 504);
        throw e;
      }
      rearm();
      if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true });
      const { events, rest } = drainSse(buffer);
      buffer = rest;
      for (const ev of events) {
        const chunk = mapAnthropicEvent(ev);
        if (chunk) yield chunk;
      }
    }
  } finally {
    clearTimeout(idle);
  }
}
