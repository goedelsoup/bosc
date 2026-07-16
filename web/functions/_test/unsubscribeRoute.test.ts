// Tier A integration test for GET /api/auth/unsubscribe (#939 E2, moved to Lakebase in #1171).
// The signed token is the credential (no login); on success the category is removed from the user's
// stored prefs. Drives the handler with a real in-memory Postgres (pglite) bound as AUTH_DB.

import { beforeEach, describe, expect, it } from "vitest";
import { onRequestGet as unsubscribe } from "@watermark/functions/api/auth/unsubscribe";
import { getPrefs, setNotifications } from "@watermark/functions/api/_lib/authStore";
import { signUnsubToken } from "@watermark/functions/api/_lib/unsub";
import { type FakePg, fakePg } from "./_routeHarness";

const BASE = "https://bosc.test/api/auth/unsubscribe";
const SECRET = "test-unsub-secret-32-bytes-long!!";
const SUB = "user-sub-unsub";

let db: FakePg;
// Generous hook timeout: the first pglite WASM boot (per worker) can be slow under full-suite
// parallelism, and the default 10s hook timeout is tighter than the 15s per-test one.
beforeEach(async () => {
  db = await fakePg();
  await setNotifications(
    db,
    SUB,
    { sites: [], categories: ["tip", "correction"], frequency: "immediate", email_verified: false },
    "2026-01-01T00:00:00.000Z",
  );
}, 30000);

function req(token: string | null): Request {
  const url = token === null ? BASE : `${BASE}?token=${encodeURIComponent(token)}`;
  return new Request(url);
}

describe("GET /api/auth/unsubscribe", () => {
  it("returns 503 when UNSUB_SECRET is not configured", async () => {
    const res = await unsubscribe({ request: req("x"), env: { AUTH_DB: db } as never });
    expect(res.status).toBe(503);
  });

  it("returns 503 when the prefs store is not bound", async () => {
    const res = await unsubscribe({ request: req("x"), env: { UNSUB_SECRET: SECRET } as never });
    expect(res.status).toBe(503);
  });

  it("returns 400 when the token is missing", async () => {
    const res = await unsubscribe({
      request: req(null),
      env: { UNSUB_SECRET: SECRET, AUTH_DB: db } as never,
    });
    expect(res.status).toBe(400);
  });

  it("returns 400 for an invalid token", async () => {
    const res = await unsubscribe({
      request: req("not.a.valid.token"),
      env: { UNSUB_SECRET: SECRET, AUTH_DB: db } as never,
    });
    expect(res.status).toBe(400);
  });

  it("removes the category from stored prefs and persists it", async () => {
    const token = await signUnsubToken(SUB, "tip", SECRET);
    const res = await unsubscribe({
      request: req(token),
      env: { UNSUB_SECRET: SECRET, AUTH_DB: db } as never,
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body).toMatchObject({ ok: true, removed: "tip", remaining: ["correction"] });

    // The write landed in Postgres.
    const prefs = await getPrefs(db, SUB);
    expect(prefs.notifications.categories).toEqual(["correction"]);
  });

  it("succeeds without materializing rows when the token's sub has no prefs", async () => {
    const token = await signUnsubToken("stranger-sub", "tip", SECRET);
    const res = await unsubscribe({
      request: req(token),
      env: { UNSUB_SECRET: SECRET, AUTH_DB: db } as never,
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body).toMatchObject({ ok: true, removed: "tip", remaining: [] });

    // No users/prefs row was created for the unknown sub (only the seeded SUB exists).
    const users = await db.query<{ sub: string }>("SELECT sub FROM users");
    expect(users.map((u) => u.sub)).toEqual([SUB]);
  });
});
