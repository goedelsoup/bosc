// Unit tests for the Lakebase auth prefs + role-audit store (#1171) — exercised against a real
// in-memory Postgres (pglite) with the committed migrations applied, so a schema/store drift fails.

import { describe, expect, it } from "vitest";
import {
  type AuditEntry,
  getPrefs,
  listAuditEntries,
  type NotifCategory,
  setDisplayName,
  setNotifications,
  unsubscribeCategory,
  writeAuditEntry,
} from "@watermark/functions/api/_lib/authStore";
import { type FakePg, fakePg } from "./_routeHarness";

const NOW = "2026-07-04T12:00:00.000Z";

function notifs(
  over: Partial<{ sites: string[]; categories: NotifCategory[]; frequency: "immediate" | "daily" }> = {},
) {
  return { sites: [], categories: [], frequency: "immediate" as const, email_verified: false, ...over };
}

async function count(db: FakePg, table: string): Promise<number> {
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
});

describe("setNotifications / setDisplayName", () => {
  it("round-trips a stored profile + notifications", async () => {
    const db = await fakePg();
    await setNotifications(
      db,
      "sub-1",
      notifs({ sites: ["lima", "fort-wayne"], categories: ["tip", "correction"], frequency: "daily" }),
      NOW,
      "alice@example.com",
    );
    await setDisplayName(db, "sub-1", "Alice", NOW, "alice@example.com");
    const prefs = await getPrefs(db, "sub-1");
    expect(prefs.display_name).toBe("Alice");
    expect(prefs.notifications.sites).toEqual(["lima", "fort-wayne"]);
    expect(prefs.notifications.categories).toEqual(["tip", "correction"]);
    expect(prefs.notifications.frequency).toBe("daily");
    // email_verified is JWT-derived, never stored → always the false default on read.
    expect(prefs.notifications.email_verified).toBe(false);
  });

  it("upserts a backing users row (FK for the prefs row)", async () => {
    const db = await fakePg();
    await setNotifications(db, "sub-u", notifs(), NOW, "u@example.com");
    const users = await db.query<{ sub: string; email: string | null }>("SELECT sub, email FROM users");
    expect(users).toEqual([{ sub: "sub-u", email: "u@example.com" }]);
    expect(await count(db, "user_prefs")).toBe(1);
  });

  it("is idempotent — a second write updates in place, no duplicate rows", async () => {
    const db = await fakePg();
    await setDisplayName(db, "sub-2", "First", NOW, "e@example.com");
    await setDisplayName(db, "sub-2", "Second", "2026-07-04T13:00:00.000Z");
    expect(await count(db, "user_prefs")).toBe(1);
    expect((await getPrefs(db, "sub-2")).display_name).toBe("Second");
  });

  it("a null email does not clobber a previously-known email", async () => {
    const db = await fakePg();
    await setNotifications(db, "sub-3", notifs(), NOW, "keep@example.com");
    await setNotifications(db, "sub-3", notifs(), "2026-07-04T14:00:00.000Z"); // no email
    const users = await db.query<{ email: string | null }>("SELECT email FROM users WHERE sub = $1", [
      "sub-3",
    ]);
    expect(users[0].email).toBe("keep@example.com");
  });

  it("setDisplayName(null) clears the name", async () => {
    const db = await fakePg();
    await setDisplayName(db, "sub-4", "Named", NOW);
    await setDisplayName(db, "sub-4", null, "2026-07-04T15:00:00.000Z");
    expect((await getPrefs(db, "sub-4")).display_name).toBeUndefined();
  });

  // Field-scoped writes: the two account endpoints touch disjoint columns and can't clobber.
  it("setNotifications does not clobber a stored display_name", async () => {
    const db = await fakePg();
    await setDisplayName(db, "sub-5", "Keep Me", NOW);
    await setNotifications(db, "sub-5", notifs({ frequency: "daily" }), "2026-07-04T16:00:00.000Z");
    const prefs = await getPrefs(db, "sub-5");
    expect(prefs.display_name).toBe("Keep Me");
    expect(prefs.notifications.frequency).toBe("daily");
  });

  it("setDisplayName does not clobber stored notifications", async () => {
    const db = await fakePg();
    await setNotifications(db, "sub-6", notifs({ categories: ["tip"] }), NOW);
    await setDisplayName(db, "sub-6", "New Name", "2026-07-04T17:00:00.000Z");
    const prefs = await getPrefs(db, "sub-6");
    expect(prefs.display_name).toBe("New Name");
    expect(prefs.notifications.categories).toEqual(["tip"]);
  });
});

describe("unsubscribeCategory", () => {
  it("removes a category from an existing prefs row and returns the remainder", async () => {
    const db = await fakePg();
    await setNotifications(db, "sub-un", notifs({ categories: ["tip", "correction"] }), NOW);
    const remaining = await unsubscribeCategory(db, "sub-un", "tip", "2026-07-04T18:00:00.000Z");
    expect(remaining).toEqual(["correction"]);
    expect((await getPrefs(db, "sub-un")).notifications.categories).toEqual(["correction"]);
  });

  it("is a success no-op when the user has no prefs row — never materializes identity rows", async () => {
    const db = await fakePg();
    const remaining = await unsubscribeCategory(db, "ghost-sub", "tip", NOW);
    expect(remaining).toEqual([]);
    expect(await count(db, "user_prefs")).toBe(0);
    expect(await count(db, "users")).toBe(0);
  });

  it("is idempotent — removing an absent category leaves the rest intact", async () => {
    const db = await fakePg();
    await setNotifications(db, "sub-idem", notifs({ categories: ["correction"] }), NOW);
    const remaining = await unsubscribeCategory(db, "sub-idem", "tip", "2026-07-04T19:00:00.000Z");
    expect(remaining).toEqual(["correction"]);
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

  it("orders deterministically when timestamps tie (id tiebreak, stable across calls)", async () => {
    const db = await fakePg();
    const at = "2026-06-29T12:00:00.000Z";
    await writeAuditEntry(db, { ...BASE_ENTRY, at }, "id-1");
    await writeAuditEntry(db, { ...BASE_ENTRY, at }, "id-2");
    await writeAuditEntry(db, { ...BASE_ENTRY, at }, "id-3");
    const first = (await listAuditEntries(db, "target-sub")).length;
    // Same query twice yields the identical order (no reshuffle on same-`at` rows).
    const a = await listAuditEntries(db, "target-sub", 2);
    const b = await listAuditEntries(db, "target-sub", 2);
    expect(first).toBe(3);
    expect(a).toEqual(b);
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
    expect(await count(db, "audit_log")).toBe(1);
  });
});
