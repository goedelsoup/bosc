// Unit tests for the Lakebase auth prefs + role-audit store (#1171) — exercised against a real
// in-memory Postgres (pglite) with the committed migrations applied, so a schema/store drift fails.

import { describe, expect, it } from "vitest";
import {
  type AuditEntry,
  getPrefs,
  listAuditEntries,
  putPrefs,
  writeAuditEntry,
} from "@fn/api/_lib/authStore";
import { type FakePg, fakePg } from "./_routeHarness";

const NOW = "2026-07-04T12:00:00.000Z";

async function ids(db: FakePg, table: string): Promise<number> {
  const rows = await db.query<{ n: number }>(`SELECT count(*)::int AS n FROM ${table}`);
  return rows[0].n;
}

describe("getPrefs", () => {
  it("returns defaults when no row exists", async () => {
    const db = await fakePg();
    const prefs = await getPrefs(db, "no-such-sub");
    expect(prefs.display_name).toBeUndefined();
    expect(prefs.notifications).toEqual({
      sites: [],
      categories: [],
      frequency: "immediate",
      email_verified: false,
    });
  });

  it("round-trips a stored profile + notifications", async () => {
    const db = await fakePg();
    await putPrefs(
      db,
      "sub-1",
      {
        display_name: "Alice",
        notifications: {
          sites: ["lima", "fort-wayne"],
          categories: ["tip", "correction"],
          frequency: "daily",
          email_verified: true, // must NOT be persisted
        },
      },
      NOW,
      "alice@example.com",
    );
    const prefs = await getPrefs(db, "sub-1");
    expect(prefs.display_name).toBe("Alice");
    expect(prefs.notifications.sites).toEqual(["lima", "fort-wayne"]);
    expect(prefs.notifications.categories).toEqual(["tip", "correction"]);
    expect(prefs.notifications.frequency).toBe("daily");
    // email_verified is JWT-derived, never stored → always the false default on read.
    expect(prefs.notifications.email_verified).toBe(false);
  });
});

describe("putPrefs", () => {
  it("upserts a backing users row (FK for the prefs row)", async () => {
    const db = await fakePg();
    await putPrefs(
      db,
      "sub-u",
      { notifications: { sites: [], categories: [], frequency: "immediate", email_verified: false } },
      NOW,
      "u@example.com",
    );
    const users = await db.query<{ sub: string; email: string | null }>("SELECT sub, email FROM users");
    expect(users).toEqual([{ sub: "sub-u", email: "u@example.com" }]);
    expect(await ids(db, "user_prefs")).toBe(1);
  });

  it("is idempotent — a second write updates in place, no duplicate rows", async () => {
    const db = await fakePg();
    const base = {
      notifications: { sites: [], categories: [], frequency: "immediate" as const, email_verified: false },
    };
    await putPrefs(db, "sub-2", { ...base, display_name: "First" }, NOW, "e@example.com");
    await putPrefs(db, "sub-2", { ...base, display_name: "Second" }, "2026-07-04T13:00:00.000Z");
    expect(await ids(db, "user_prefs")).toBe(1);
    const prefs = await getPrefs(db, "sub-2");
    expect(prefs.display_name).toBe("Second");
  });

  it("a null email does not clobber a previously-known email", async () => {
    const db = await fakePg();
    const base = {
      notifications: { sites: [], categories: [], frequency: "immediate" as const, email_verified: false },
    };
    await putPrefs(db, "sub-3", base, NOW, "keep@example.com");
    // e.g. the unsubscribe path, which has no email.
    await putPrefs(db, "sub-3", base, "2026-07-04T14:00:00.000Z");
    const users = await db.query<{ email: string | null }>("SELECT email FROM users WHERE sub = $1", [
      "sub-3",
    ]);
    expect(users[0].email).toBe("keep@example.com");
  });

  it("clears display_name when omitted", async () => {
    const db = await fakePg();
    const base = {
      notifications: { sites: [], categories: [], frequency: "immediate" as const, email_verified: false },
    };
    await putPrefs(db, "sub-4", { ...base, display_name: "Named" }, NOW);
    await putPrefs(db, "sub-4", base, "2026-07-04T15:00:00.000Z");
    const prefs = await getPrefs(db, "sub-4");
    expect(prefs.display_name).toBeUndefined();
  });
});

const BASE_ENTRY: AuditEntry = {
  actor: "actor-sub",
  target: "target-sub",
  action: "set-groups",
  before: ["standard"],
  after: ["admin"],
  at: "2026-06-29T12:00:00.000Z",
};

describe("writeAuditEntry + listAuditEntries", () => {
  it("stores and reads back an entry", async () => {
    const db = await fakePg();
    await writeAuditEntry(db, BASE_ENTRY, "id-1");
    const entries = await listAuditEntries(db, "target-sub");
    expect(entries).toEqual([BASE_ENTRY]);
  });

  it("returns entries newest-first (SELECT ... ORDER BY at DESC)", async () => {
    const db = await fakePg();
    await writeAuditEntry(db, { ...BASE_ENTRY, at: "2026-06-29T10:00:00.000Z" }, "id-a");
    await writeAuditEntry(db, { ...BASE_ENTRY, at: "2026-06-29T12:00:00.000Z" }, "id-b");
    const entries = await listAuditEntries(db, "target-sub");
    expect(entries.map((e) => e.at)).toEqual(["2026-06-29T12:00:00.000Z", "2026-06-29T10:00:00.000Z"]);
  });

  it("isolates entries by target sub", async () => {
    const db = await fakePg();
    await writeAuditEntry(db, { ...BASE_ENTRY, target: "sub-a" }, "id-a");
    await writeAuditEntry(db, { ...BASE_ENTRY, target: "sub-b" }, "id-b");
    const forA = await listAuditEntries(db, "sub-a");
    expect(forA).toHaveLength(1);
    expect(forA[0].target).toBe("sub-a");
  });

  it("honors the limit (most recent N)", async () => {
    const db = await fakePg();
    for (let i = 0; i < 5; i++) {
      await writeAuditEntry(db, { ...BASE_ENTRY, at: `2026-06-29T1${i}:00:00.000Z` }, `id-${i}`);
    }
    const entries = await listAuditEntries(db, "target-sub", 2);
    expect(entries.map((e) => e.at)).toEqual(["2026-06-29T14:00:00.000Z", "2026-06-29T13:00:00.000Z"]);
  });

  it("returns [] when no entries exist", async () => {
    const db = await fakePg();
    expect(await listAuditEntries(db, "nobody")).toEqual([]);
  });

  it("is best-effort — a write failure is swallowed, not thrown", async () => {
    const db = await fakePg();
    // A duplicate primary key would throw inside the INSERT; writeAuditEntry must absorb it.
    await writeAuditEntry(db, BASE_ENTRY, "dup");
    await expect(writeAuditEntry(db, BASE_ENTRY, "dup")).resolves.toBeUndefined();
    // The first write survived; the second (colliding) one was dropped.
    expect(await ids(db, "audit_log")).toBe(1);
  });
});
