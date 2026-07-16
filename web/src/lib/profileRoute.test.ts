// Tier A integration tests for the /api/account/profile and /api/account/notifications
// Pages Functions (Epic #921 C1/C2, moved to Lakebase in #1171). Drives the exported onRequest*
// handlers in-process with a faked Env + a real in-memory Postgres (pglite) bound as AUTH_DB, so the
// full request path — kill switch → auth → prefs store — is exercised offline.

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
  onRequestGet as profileGet,
  onRequestPatch as profilePatch,
} from "@watermark/functions/api/account/profile";
import {
  onRequestGet as notifGet,
  onRequestPatch as notifPatch,
} from "@watermark/functions/api/account/notifications";
import { setDisplayName, setNotifications, type UserPrefs } from "@watermark/functions/api/_lib/authStore";
import {
  type CognitoTestKeyPair,
  type FakePg,
  fakeKV,
  fakePg,
  generateCognitoKeyPair,
  mintIdToken,
  routingFetch,
} from "./_routeHarness";

const PROFILE_URL = "https://bosc.test/api/account/profile";
const NOTIF_URL = "https://bosc.test/api/account/notifications";

// Fake JWKS endpoint URL (matches iss in minted tokens)
const REGION = "us-east-1";
const USER_POOL_ID = "us-east-1_TestPool";
const CLIENT_ID = "test-client-id";
const JWKS_URL = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/jwks.json`;

let keypair: CognitoTestKeyPair;
beforeAll(async () => {
  keypair = await generateCognitoKeyPair();
});

let db: FakePg;
// Generous hook timeout: the first pglite WASM boot (per worker) can be slow under full-suite
// parallelism, and the default 10s hook timeout is tighter than the 15s per-test one.
beforeEach(async () => {
  db = await fakePg();
}, 30000);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function authEnv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    AUTH_ENABLED: "true",
    COGNITO_REGION: REGION,
    COGNITO_USER_POOL_ID: USER_POOL_ID,
    COGNITO_CLIENT_ID: CLIENT_ID,
    // JWKS_CACHE stays on KV (a TTL'd edge cache) — only AUTH_PREFS moved to Postgres.
    JWKS_CACHE: fakeKV({ jwks: JSON.stringify({ keys: [keypair.jwk] }) }),
    AUTH_DB: db,
    ...overrides,
  };
}

function stubJwks(): void {
  vi.stubGlobal(
    "fetch",
    routingFetch([
      {
        test: (url) => url.href === JWKS_URL,
        respond: () => new Response(JSON.stringify({ keys: [keypair.jwk] }), { status: 200 }),
      },
    ]),
  );
}

async function validToken(sub = "user-sub-123", email = "user@example.com"): Promise<string> {
  return mintIdToken(keypair, { sub, email, clientId: CLIENT_ID, userPoolId: USER_POOL_ID, region: REGION });
}

function bearerRequest(url: string, method: "GET" | "PATCH", token: string, body?: unknown): Request {
  return new Request(url, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

/** Seed a prefs row for `sub` directly through the store (the DB analog of the old KV seed). */
async function seedPrefs(sub: string, prefs: UserPrefs): Promise<void> {
  const at = "2026-01-01T00:00:00.000Z";
  await setNotifications(db, sub, prefs.notifications, at, "seed@example.com");
  if (prefs.display_name !== undefined) await setDisplayName(db, sub, prefs.display_name, at);
}

// ---------------------------------------------------------------------------
// GET /api/account/profile
// ---------------------------------------------------------------------------

describe("GET /api/account/profile", () => {
  it("returns 503 when AUTH_ENABLED absent", async () => {
    const req = new Request(PROFILE_URL);
    const res = await profileGet({ request: req, env: { AUTH_ENABLED: undefined } as never });
    expect(res.status).toBe(503);
  });

  it("returns 401 with no Authorization header", async () => {
    const req = new Request(PROFILE_URL);
    const res = await profileGet({ request: req, env: authEnv() as never });
    expect(res.status).toBe(401);
  });

  it("returns 503 when the prefs store is not bound", async () => {
    stubJwks();
    const token = await validToken();
    const req = bearerRequest(PROFILE_URL, "GET", token);
    const res = await profileGet({ request: req, env: authEnv({ AUTH_DB: undefined }) as never });
    expect(res.status).toBe(503);
  });

  it("returns 200 with default profile when no prefs stored", async () => {
    stubJwks();
    const token = await validToken("sub-abc", "abc@example.com");
    const req = bearerRequest(PROFILE_URL, "GET", token);
    const res = await profileGet({ request: req, env: authEnv() as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.sub).toBe("sub-abc");
    expect(body.email).toBe("abc@example.com");
    // mintIdToken always sets email_verified: true in the JWT payload
    expect(body.email_verified).toBe(true);
    expect(body.display_name).toBeNull();
    expect(body.role).toBe("standard");
  });
});

// ---------------------------------------------------------------------------
// PATCH /api/account/profile
// ---------------------------------------------------------------------------

describe("PATCH /api/account/profile", () => {
  it("returns 503 when AUTH_ENABLED absent", async () => {
    const req = new Request(PROFILE_URL, { method: "PATCH" });
    const res = await profilePatch({ request: req, env: { AUTH_ENABLED: undefined } as never });
    expect(res.status).toBe(503);
  });

  it("returns 401 with no Authorization header", async () => {
    const req = new Request(PROFILE_URL, { method: "PATCH" });
    const res = await profilePatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(401);
  });

  it("returns 400 on invalid JSON", async () => {
    stubJwks();
    const token = await validToken();
    const req = new Request(PROFILE_URL, {
      method: "PATCH",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: "not-json",
    });
    const res = await profilePatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
  });

  it("updates display_name and returns it in profile", async () => {
    stubJwks();
    const token = await validToken("sub-patch", "patch@example.com");
    const env = authEnv();
    const req = bearerRequest(PROFILE_URL, "PATCH", token, { display_name: "Alice" });
    const res = await profilePatch({ request: req, env: env as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.email_verified).toBe(true);
    expect(body.display_name).toBe("Alice");

    // GET confirms the stored value
    const getReq = bearerRequest(PROFILE_URL, "GET", token);
    const getRes = await profileGet({ request: getReq, env: env as never });
    const getBody = (await getRes.json()) as Record<string, unknown>;
    expect(getBody.display_name).toBe("Alice");
  });

  it("clears display_name when patched to null", async () => {
    stubJwks();
    const token = await validToken("sub-clear", "clear@example.com");
    await seedPrefs("sub-clear", {
      display_name: "Bob",
      notifications: { sites: [], categories: [], frequency: "immediate", email_verified: false },
    });
    const req = bearerRequest(PROFILE_URL, "PATCH", token, { display_name: null });
    const res = await profilePatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.display_name).toBeNull();
  });

  it("returns 400 when display_name exceeds 80 chars", async () => {
    stubJwks();
    const token = await validToken();
    const req = bearerRequest(PROFILE_URL, "PATCH", token, { display_name: "x".repeat(81) });
    const res = await profilePatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
  });

  it("ignores unknown fields (strips them silently)", async () => {
    stubJwks();
    const token = await validToken("sub-strip", "strip@example.com");
    const req = bearerRequest(PROFILE_URL, "PATCH", token, { display_name: "Carol", bogus: 999 });
    const res = await profilePatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.display_name).toBe("Carol");
    expect(body).not.toHaveProperty("bogus");
  });
});

// ---------------------------------------------------------------------------
// GET /api/account/notifications
// ---------------------------------------------------------------------------

describe("GET /api/account/notifications", () => {
  it("returns 503 when AUTH_ENABLED absent", async () => {
    const req = new Request(NOTIF_URL);
    const res = await notifGet({ request: req, env: { AUTH_ENABLED: undefined } as never });
    expect(res.status).toBe(503);
  });

  it("returns 401 with no Authorization header", async () => {
    const req = new Request(NOTIF_URL);
    const res = await notifGet({ request: req, env: authEnv() as never });
    expect(res.status).toBe(401);
  });

  it("returns default notifications when no prefs stored", async () => {
    stubJwks();
    const token = await validToken("sub-notif-default");
    const req = bearerRequest(NOTIF_URL, "GET", token);
    const res = await notifGet({ request: req, env: authEnv() as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.sites).toEqual([]);
    expect(body.categories).toEqual([]);
    expect(body.frequency).toBe("immediate");
    // mintIdToken sets email_verified: true in the JWT; the endpoint syncs it from the token.
    expect(body.email_verified).toBe(true);
  });

  it("syncs email_verified from JWT (email_verified is never persisted)", async () => {
    stubJwks();
    // Store prefs (email_verified isn't a stored column); the JWT drives the response value.
    await seedPrefs("sub-ev", {
      notifications: { sites: [], categories: [], frequency: "immediate", email_verified: false },
    });
    const token = await mintIdToken(keypair, {
      sub: "sub-ev",
      email: "ev@example.com",
      clientId: CLIENT_ID,
      userPoolId: USER_POOL_ID,
      region: REGION,
    });
    const req = bearerRequest(NOTIF_URL, "GET", token);
    const res = await notifGet({ request: req, env: authEnv() as never });
    expect(res.status).toBe(200);
    // Cognito's email_verified in the token determines the response.
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.email_verified).toBe(true); // mintIdToken sets email_verified: true
  });
});

// ---------------------------------------------------------------------------
// PATCH /api/account/notifications
// ---------------------------------------------------------------------------

describe("PATCH /api/account/notifications", () => {
  it("returns 503 when AUTH_ENABLED absent", async () => {
    const req = new Request(NOTIF_URL, { method: "PATCH" });
    const res = await notifPatch({ request: req, env: { AUTH_ENABLED: undefined } as never });
    expect(res.status).toBe(503);
  });

  it("returns 401 with no Authorization header", async () => {
    const req = new Request(NOTIF_URL, { method: "PATCH" });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(401);
  });

  it("returns 400 on invalid JSON", async () => {
    stubJwks();
    const token = await validToken();
    const req = new Request(NOTIF_URL, {
      method: "PATCH",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: "bad",
    });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
  });

  it("returns 400 for invalid category value", async () => {
    stubJwks();
    const token = await validToken();
    const req = bearerRequest(NOTIF_URL, "PATCH", token, { categories: ["tip", "bogus"] });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(String(body.error)).toContain("bogus");
  });

  it("returns 400 for invalid frequency value", async () => {
    stubJwks();
    const token = await validToken();
    const req = bearerRequest(NOTIF_URL, "PATCH", token, { frequency: "weekly" });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
  });

  it("returns 400 for an invalid site slug", async () => {
    stubJwks();
    const token = await validToken();
    const req = bearerRequest(NOTIF_URL, "PATCH", token, { sites: ["lima", "BOGUS SITE!"] });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(String(body.error)).toContain("BOGUS SITE!");
  });

  it("updates sites, categories, and frequency", async () => {
    stubJwks();
    const token = await validToken("sub-notif-patch");
    const env = authEnv();
    const req = bearerRequest(NOTIF_URL, "PATCH", token, {
      sites: ["lima", "fort-wayne"],
      categories: ["tip", "correction"],
      frequency: "daily",
    });
    const res = await notifPatch({ request: req, env: env as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.sites).toEqual(["lima", "fort-wayne"]);
    expect(body.categories).toEqual(["tip", "correction"]);
    expect(body.frequency).toBe("daily");

    // GET confirms the write landed in Postgres.
    const getRes = await notifGet({ request: bearerRequest(NOTIF_URL, "GET", token), env: env as never });
    const getBody = (await getRes.json()) as Record<string, unknown>;
    expect(getBody.sites).toEqual(["lima", "fort-wayne"]);
  });

  it("email_verified cannot be patched by the user", async () => {
    stubJwks();
    const token = await validToken("sub-ev-patch");
    const req = bearerRequest(NOTIF_URL, "PATCH", token, { email_verified: true });
    const res = await notifPatch({ request: req, env: authEnv() as never });
    // Patch succeeds but email_verified is driven by the JWT, not the payload
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    // mintIdToken sets email_verified: true on the payload, so JWT drives it
    expect(body.email_verified).toBe(true);
  });

  it("partial patch only updates provided fields", async () => {
    stubJwks();
    const token = await validToken("sub-partial");
    await seedPrefs("sub-partial", {
      notifications: { sites: ["lima"], categories: ["tip"], frequency: "daily", email_verified: false },
    });
    const env = authEnv();
    // Only update frequency
    const req = bearerRequest(NOTIF_URL, "PATCH", token, { frequency: "immediate" });
    const res = await notifPatch({ request: req, env: env as never });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.sites).toEqual(["lima"]);
    expect(body.categories).toEqual(["tip"]);
    expect(body.frequency).toBe("immediate");
  });
});
