// Per-IP rate limiting for the submissions endpoint (Phase 5), backed by Cloudflare
// KV. A fixed-window counter: one key per (ip, window), auto-expiring. KV is eventually
// consistent, so this is a *soft* abuse-dampener layered behind Turnstile, not a hard
// guarantee — good enough for a low-traffic tips form.
//
// Optional by design: if no KV namespace is bound (`env.RATE_LIMIT` absent), the caller
// skips rate limiting entirely, and any KV error here fails **open** (allow) — Turnstile
// remains the primary gate, so a KV outage must not drop legitimate submissions.

/** The slice of the Workers KV API we use (avoids a dep on @cloudflare/workers-types). */
export interface KVLike {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
}

export interface RateLimitConfig {
  /** Max submissions allowed per IP per window. */
  max: number;
  /** Window length in seconds (KV requires ≥ 60). */
  windowSec: number;
}

export const DEFAULT_RATE_LIMIT: RateLimitConfig = { max: 5, windowSec: 3600 };

export interface RateLimitResult {
  allowed: boolean;
  /** Seconds until the current window resets (for a `Retry-After` header). */
  retryAfter: number;
}

/** Deterministic key for the fixed window containing `nowSec`. Pure — unit-tested. */
export function windowKey(ip: string, nowSec: number, windowSec: number): string {
  const windowId = Math.floor(nowSec / windowSec);
  return `rl:${ip}:${windowId}`;
}

/** Seconds remaining in the current window. Pure. */
export function secondsUntilReset(nowSec: number, windowSec: number): number {
  return windowSec - (nowSec % windowSec);
}

/**
 * Check + increment the counter for `ip`. Fails open on any KV error. The TTL slightly
 * outlives the window so the windowed key is reaped on its own.
 */
export async function checkRateLimit(
  kv: KVLike,
  ip: string,
  nowSec: number,
  cfg: RateLimitConfig = DEFAULT_RATE_LIMIT,
): Promise<RateLimitResult> {
  const retryAfter = secondsUntilReset(nowSec, cfg.windowSec);
  try {
    const key = windowKey(ip, nowSec, cfg.windowSec);
    const current = Number((await kv.get(key)) ?? "0");
    if (current >= cfg.max) return { allowed: false, retryAfter };
    await kv.put(key, String(current + 1), { expirationTtl: cfg.windowSec * 2 });
    return { allowed: true, retryAfter };
  } catch {
    return { allowed: true, retryAfter }; // fail open — Turnstile is the primary gate
  }
}
