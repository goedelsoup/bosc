// Immutable role-change audit trail (#937 D3).
// Records are stored in the AUTH_PREFS KV namespace under keys:
//   audit:role:<target-sub>:<iso-timestamp>
// Lexicographic ordering makes prefix-scans chronologically sorted per user.
// Writes are best-effort: a KV failure must NOT roll back the Cognito change.

import type { KVLike } from "./ratelimit";

/** KVLike extended with the list() method needed for prefix scans. */
export interface KVListable extends KVLike {
  list(options?: { prefix?: string; limit?: number; cursor?: string }): Promise<{
    keys: Array<{ name: string }>;
    list_complete: boolean;
    cursor?: string;
  }>;
}

export type AuditAction = "set-groups" | "set-admin-sites" | "grant-early-access" | "revoke-early-access";

export interface AuditEntry {
  actor: string;
  target: string;
  action: AuditAction;
  before: string[];
  after: string[];
  at: string;
}

function auditKey(targetSub: string, at: string): string {
  return `audit:role:${targetSub}:${at}`;
}

/** Write an audit entry to KV (best-effort; logs on failure but does not throw). */
export async function writeAuditEntry(kv: KVLike, entry: AuditEntry): Promise<void> {
  const key = auditKey(entry.target, entry.at);
  try {
    await kv.put(key, JSON.stringify(entry));
  } catch (e) {
    console.error("audit write failed", key, e);
  }
}

/** List the most recent audit entries for a user (up to `limit`, default 20). */
export async function listAuditEntries(kv: KVListable, targetSub: string, limit = 20): Promise<AuditEntry[]> {
  const prefix = `audit:role:${targetSub}:`;
  // Page through all keys so we see the full history, then take the tail — kv.list({ limit })
  // returns the OLDEST page, not the newest.
  const allKeys: Array<{ name: string }> = [];
  let cursor: string | undefined;
  while (true) {
    const page = await kv.list({ prefix, ...(cursor ? { cursor } : {}) });
    allKeys.push(...page.keys);
    if (page.list_complete) break;
    cursor = page.cursor;
  }
  // Keys are ascending (oldest-first); slice the tail for the most recent entries.
  const tail = allKeys.slice(-limit);
  const entries: AuditEntry[] = [];
  for (const { name } of tail) {
    const raw = await kv.get(name);
    if (!raw) continue;
    try {
      entries.push(JSON.parse(raw) as AuditEntry);
    } catch {
      // skip malformed
    }
  }
  return entries.reverse();
}
