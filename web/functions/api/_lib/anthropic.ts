// Minimal Anthropic Messages API client over `fetch` — no SDK, Web platform globals
// only, so it runs on the Cloudflare Workers runtime (the submit endpoint signs its own
// JWTs the same way rather than pulling a dependency). Non-streaming here; the SSE path
// is added in #214 (functions/api/_lib/anthropicStream.ts can reuse this shape).
// https://docs.anthropic.com/en/api/messages

import { fetchWithTimeout, isTimeoutError } from "./http";

// Default Messages API endpoint. Overridable per-request (`MessageRequest.apiUrl`, fed
// from the ANTHROPIC_API_BASE var) so the local dev stack can point at a mock origin —
// prod leaves it unset and hits api.anthropic.com. See frontend/scripts/dev-mocks.mjs.
export const API_URL = "https://api.anthropic.com/v1/messages";
export const API_VERSION = "2023-06-01";

export interface AnthropicUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface MessageRequest {
  apiKey: string;
  model: string;
  system: string;
  /** A single user turn is all /api/ask needs; the array keeps the door open. */
  messages: { role: "user" | "assistant"; content: string }[];
  maxTokens: number;
  /**
   * Sent only when explicitly set. Newer models (e.g. claude-opus-4-8) deprecate and
   * reject `temperature` outright, so omitting it lets the model apply its own default;
   * pass a value only for an older model that still honors it.
   */
  temperature?: number;
  /** Override the Messages API endpoint (local dev mock). Defaults to api.anthropic.com. */
  apiUrl?: string;
}

export interface MessageResult {
  text: string;
  usage?: AnthropicUsage;
  stopReason?: string;
}

interface RawResponse {
  content?: { type: string; text?: string }[];
  usage?: AnthropicUsage;
  stop_reason?: string;
  error?: { type?: string; message?: string };
}

/** Thrown on a non-2xx Messages API response; carries the upstream status for the route. */
export class AnthropicError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AnthropicError";
  }
}

export async function createMessage(req: MessageRequest): Promise<MessageResult> {
  let res: Response;
  try {
    res = await fetchWithTimeout(req.apiUrl || API_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": req.apiKey,
        "anthropic-version": API_VERSION,
      },
      body: JSON.stringify({
        model: req.model,
        max_tokens: req.maxTokens,
        // Only include `temperature` when a caller set one — newer models reject it (see MessageRequest).
        ...(req.temperature !== undefined ? { temperature: req.temperature } : {}),
        system: req.system,
        messages: req.messages,
      }),
    });
  } catch (e) {
    if (isTimeoutError(e)) throw new AnthropicError("Anthropic request timed out", 504);
    throw e;
  }

  const data = (await res.json().catch(() => null)) as RawResponse | null;
  if (!res.ok) {
    throw new AnthropicError(data?.error?.message ?? `Anthropic API error ${res.status}`, res.status);
  }
  const text = (data?.content ?? [])
    .filter((b) => b.type === "text" && typeof b.text === "string")
    .map((b) => b.text as string)
    .join("");
  return { text, usage: data?.usage, stopReason: data?.stop_reason };
}
