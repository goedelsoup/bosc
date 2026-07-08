// Tier A integration test for the interactive site-contacts Pages Functions
// (functions/api/petition/connect.ts, bulletin.ts, admin/contacts.ts): drive the exported handlers
// end-to-end with a faked Env (a real in-memory Postgres/pglite + a minted Cognito token for the
// admin path), so the full path — kill switch → (auth) → rate-limit → validation → Lakebase write —
// runs offline. Turnstile is skipped (no TURNSTILE_SECRET), matching the dark-launch config.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ContactsEnv } from "@fn/api/_lib/contactsRoute";
import { onRequestGet as adminGet, onRequestPost as adminPost } from "@fn/api/admin/contacts";
import { onRequestGet as bulletinGet, onRequestPost as bulletinPost } from "@fn/api/bulletin";
import { onRequestGet as connectGet, onRequestPost as connectPost } from "@fn/api/petition/connect";
import {
  type CognitoTestKeyPair,
  type FakePg,
  fakePg,
  generateCognitoKeyPair,
  jsonResponse,
  mintIdToken,
  postJson,
  routingFetch,
} from "./_routeHarness";

const REGION = "us-east-2";
const POOL = "us-east-2_test";
const CLIENT = "client-123";

let keypair: CognitoTestKeyPair;
beforeEach(async () => {
  keypair = await generateCognitoKeyPair();
});
afterEach(() => vi.unstubAllGlobals());

function stubJwks(): void {
  vi.stubGlobal(
    "fetch",
    routingFetch([
      {
        test: (url) => url.href.includes("jwks.json"),
        respond: () => jsonResponse(200, { keys: [keypair.jwk] }),
      },
    ]),
  );
}

function env(db: FakePg, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    CONTACTS_ENABLED: "true",
    CONTACTS_DB: db,
    COGNITO_REGION: REGION,
    COGNITO_USER_POOL_ID: POOL,
    COGNITO_CLIENT_ID: CLIENT,
    ...overrides,
  };
}

async function bearer(sub = "user-1", groups?: string[]): Promise<Record<string, string>> {
  const token = await mintIdToken(keypair, {
    sub,
    email: `${sub}@x.com`,
    clientId: CLIENT,
    userPoolId: POOL,
    region: REGION,
    groups,
  });
  return { authorization: `Bearer ${token}` };
}

const ctx = (request: Request, e: Record<string, unknown>) => ({ request, env: e as unknown as ContactsEnv });

describe("/api/petition/connect", () => {
  it("503s when the feature is disabled", async () => {
    const db = await fakePg();
    const req = postJson("https://b.test/api/petition/connect", {
      site: "lima",
      contactId: "x",
      email: "a@b.com",
    });
    const res = await connectPost(ctx(req, env(db, { CONTACTS_ENABLED: "false" })));
    expect(res.status).toBe(503);
  });

  it("rejects a malformed email", async () => {
    const db = await fakePg();
    const req = postJson("https://b.test/api/petition/connect", {
      site: "lima",
      contactId: "x",
      email: "not-an-email",
    });
    const res = await connectPost(ctx(req, env(db)));
    expect(res.status).toBe(400);
  });

  it("records a connect (202) and reflects it in the public tally without leaking the email", async () => {
    const db = await fakePg();
    const body = {
      site: "lima",
      contactId: "allen-county-commissioners",
      email: "jane@example.com",
      displayName: "Jane Q.",
      message: "in",
    };
    const res = await connectPost(ctx(postJson("https://b.test/api/petition/connect", body), env(db)));
    expect(res.status).toBe(202);

    const tallyRes = await connectGet(
      ctx(
        new Request("https://b.test/api/petition/connect?site=lima&contactId=allen-county-commissioners"),
        env(db),
      ),
    );
    expect(tallyRes.status).toBe(200);
    const tally = await tallyRes.json();
    expect(tally.count).toBe(1);
    expect(tally.names).toEqual(["Jane Q."]);
    expect(JSON.stringify(tally)).not.toContain("example.com"); // private routing never surfaces
  });
});

describe("/api/bulletin", () => {
  it("creates a post (201) and lists it publicly without the private reply-to", async () => {
    const db = await fakePg();
    const body = {
      site: "lima",
      authorName: "Sam",
      authorContact: "sam@example.com",
      title: "Meeting",
      body: "7pm library",
    };
    const created = await bulletinPost(ctx(postJson("https://b.test/api/bulletin", body), env(db)));
    expect(created.status).toBe(201);

    const listed = await bulletinGet(ctx(new Request("https://b.test/api/bulletin?site=lima"), env(db)));
    expect(listed.status).toBe(200);
    const { posts } = await listed.json();
    expect(posts).toHaveLength(1);
    expect(posts[0].title).toBe("Meeting");
    expect(JSON.stringify(posts)).not.toContain("sam@example.com");
  });

  it("400s a post missing its body", async () => {
    const db = await fakePg();
    const res = await bulletinPost(
      ctx(postJson("https://b.test/api/bulletin", { site: "lima", authorName: "S", title: "t" }), env(db)),
    );
    expect(res.status).toBe(400);
  });
});

describe("/api/admin/contacts", () => {
  it("401s without auth", async () => {
    const db = await fakePg();
    stubJwks();
    const res = await adminGet(ctx(new Request("https://b.test/api/admin/contacts?site=lima"), env(db)));
    expect(res.status).toBe(401);
  });

  it("403s a non-admin user", async () => {
    const db = await fakePg();
    stubJwks();
    const req = new Request("https://b.test/api/admin/contacts?site=lima", { headers: await bearer("u1") });
    const res = await adminGet(ctx(req, env(db)));
    expect(res.status).toBe(403);
  });

  it("gives an admin the hand-off queue with the private email", async () => {
    const db = await fakePg();
    stubJwks();
    // Seed a connect via the public endpoint first.
    await connectPost(
      ctx(
        postJson("https://b.test/api/petition/connect", {
          site: "lima",
          contactId: "c1",
          email: "jane@example.com",
        }),
        env(db),
      ),
    );

    const req = new Request("https://b.test/api/admin/contacts?site=lima", {
      headers: await bearer("admin-1", ["admin"]),
    });
    const res = await adminGet(ctx(req, env(db)));
    expect(res.status).toBe(200);
    const out = await res.json();
    expect(out.connects).toHaveLength(1);
    expect(out.connects[0].email).toBe("jane@example.com"); // the petitioner acts on the private routing
  });

  it("lets an admin take a bulletin post down", async () => {
    const db = await fakePg();
    stubJwks();
    const created = await bulletinPost(
      ctx(
        postJson("https://b.test/api/bulletin", { site: "lima", authorName: "S", title: "t", body: "b" }),
        env(db),
      ),
    );
    const { id } = await created.json();

    const modReq = postJson(
      "https://b.test/api/admin/contacts",
      { site: "lima", action: "moderate", postId: id, moderation: "removed" },
      await bearer("admin-1", ["admin"]),
    );
    const modRes = await adminPost(ctx(modReq, env(db)));
    expect(modRes.status).toBe(200);

    const listed = await bulletinGet(ctx(new Request("https://b.test/api/bulletin?site=lima"), env(db)));
    const { posts } = await listed.json();
    expect(posts).toHaveLength(0); // removed post is gone from the public board
  });
});
