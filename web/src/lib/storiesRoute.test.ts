// Tier A integration test for the /api/stories Pages Functions (functions/api/stories.ts +
// stories/[id].ts): drive the exported handlers end-to-end with a faked Env (a real in-memory D1 +
// a stubbed catalog asset + a minted Cognito token), so the full path — kill switch → auth →
// rate-limit → server-side compile/handle-validation → transactional D1 write — runs offline.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetCatalogCache } from "@fn/api/_lib/catalogAsset";
import type { StoriesEnv } from "@fn/api/_lib/storiesRoute";
import { onRequestDelete, onRequestGet as getOne, onRequestPut } from "@fn/api/stories/[id]";
import { onRequestGet as listStoriesRoute, onRequestPost } from "@fn/api/stories";
import {
  type CognitoTestKeyPair,
  type FetchRoute,
  type FakeD1,
  fakeD1,
  generateCognitoKeyPair,
  jsonResponse,
  mintIdToken,
  postJson,
  routingFetch,
} from "./_routeHarness";

const BASE = "https://bosc.test/api/stories";
const CATALOG_URL = "https://bosc.test/stories-catalog.json";
const REGION = "us-east-2";
const POOL = "us-east-2_test";
const CLIENT = "client-123";

// One resolvable atom lives in the stubbed catalog; a Story citing it validates, one citing
// `record:lima:zzz` does not.
const CATALOG_ATOMS = [
  { handle: "record:lima:a", kind: "record", site: "lima", localId: "a", title: "A deed", feed: "records" },
];

let keypair: CognitoTestKeyPair;
beforeEach(async () => {
  keypair = await generateCognitoKeyPair();
  _resetCatalogCache();
});
afterEach(() => {
  vi.unstubAllGlobals();
  _resetCatalogCache();
});

function stubFetch(): void {
  const jwksRoute: FetchRoute = {
    test: (url) => url.href.includes("jwks.json"),
    respond: () => jsonResponse(200, { keys: [keypair.jwk] }),
  };
  const catalogRoute: FetchRoute = {
    test: (url) => url.pathname === "/stories-catalog.json",
    respond: () => jsonResponse(200, { site: "lima", version: "v1", atoms: CATALOG_ATOMS }),
  };
  vi.stubGlobal("fetch", routingFetch([jwksRoute, catalogRoute]));
}

function env(db: FakeD1, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    STORIES_ENABLED: "true",
    STORIES_DB: db,
    STORIES_CATALOG_URL: CATALOG_URL,
    COGNITO_REGION: REGION,
    COGNITO_USER_POOL_ID: POOL,
    COGNITO_CLIENT_ID: CLIENT,
    ...overrides,
  };
}

async function bearer(sub = "user-1"): Promise<Record<string, string>> {
  const token = await mintIdToken(keypair, {
    sub,
    email: `${sub}@x.com`,
    clientId: CLIENT,
    userPoolId: POOL,
    region: REGION,
  });
  return { authorization: `Bearer ${token}` };
}

const validBody = (over: Record<string, unknown> = {}) => ({
  site: "lima",
  slug: "my-story",
  title: "My Story",
  source_format: "dsl",
  source_text: '## Intro\n\n:::atom{handle="record:lima:a"}\n:::\n',
  ...over,
});

// The Pages handlers destructure { request, env, params }; the loose test `env` is narrowed to the
// route's env type here (list ignores `params`; the [id] handlers read it).
const ctx = (request: Request, e: Record<string, unknown>, params: { id: string } = { id: "" }) => ({
  request,
  env: e as unknown as StoriesEnv,
  params,
});

describe("/api/stories — guards", () => {
  it("503s when the feature is disabled", async () => {
    stubFetch();
    const req = postJson(BASE, validBody(), await bearer());
    const res = await onRequestPost(ctx(req, env(fakeD1(), { STORIES_ENABLED: "false" })));
    expect(res.status).toBe(503);
  });

  it("401s without a Bearer token", async () => {
    stubFetch();
    const res = await onRequestPost(ctx(postJson(BASE, validBody()), env(fakeD1())));
    expect(res.status).toBe(401);
  });

  it("503s when the D1 binding is absent", async () => {
    stubFetch();
    const req = postJson(BASE, validBody(), await bearer());
    const res = await onRequestPost(ctx(req, env(fakeD1(), { STORIES_DB: undefined })));
    expect(res.status).toBe(503);
  });
});

describe("/api/stories — CRUD lifecycle", () => {
  it("creates, reads, lists, updates, and deletes an owner-scoped story", async () => {
    stubFetch();
    const db = fakeD1();
    const auth = await bearer();

    // CREATE
    const created = await onRequestPost(ctx(postJson(BASE, validBody(), auth), env(db)));
    expect(created.status).toBe(201);
    const { id } = (await created.json()) as { id: string };
    expect(id).toBeTruthy();

    // READ — the compiled SDM + the derived ref are persisted.
    const got = await getOne(ctx(new Request(`${BASE}/${id}`, { headers: auth }), env(db), { id }));
    expect(got.status).toBe(200);
    const detail = (await got.json()) as {
      story: { title: string; refs: { handle: string }[]; sdm: { blocks: unknown[] } };
    };
    expect(detail.story.title).toBe("My Story");
    expect(detail.story.refs.map((r) => r.handle)).toEqual(["record:lima:a"]);
    expect(detail.story.sdm.blocks.length).toBeGreaterThan(0);

    // LIST
    const listed = await listStoriesRoute(ctx(new Request(BASE, { headers: auth }), env(db)));
    const { stories } = (await listed.json()) as { stories: { id: string }[] };
    expect(stories.map((s) => s.id)).toEqual([id]);

    // UPDATE
    const put = new Request(`${BASE}/${id}`, {
      method: "PUT",
      headers: { "content-type": "application/json", ...auth },
      body: JSON.stringify(validBody({ title: "Renamed" })),
    });
    const updated = await onRequestPut(ctx(put, env(db), { id }));
    expect(updated.status).toBe(200);
    const reread = await getOne(ctx(new Request(`${BASE}/${id}`, { headers: auth }), env(db), { id }));
    expect(((await reread.json()) as { story: { title: string } }).story.title).toBe("Renamed");

    // DELETE
    const del = new Request(`${BASE}/${id}`, { method: "DELETE", headers: auth });
    expect((await onRequestDelete(ctx(del, env(db), { id }))).status).toBe(200);
    const after = await getOne(ctx(new Request(`${BASE}/${id}`, { headers: auth }), env(db), { id }));
    expect(after.status).toBe(404);
  });
});

describe("/api/stories — validation + isolation", () => {
  it("rejects a story citing a handle that doesn't resolve (400, dangling)", async () => {
    stubFetch();
    const req = postJson(
      BASE,
      validBody({ source_text: ':::atom{handle="record:lima:zzz"}\n:::\n' }),
      await bearer(),
    );
    const res = await onRequestPost(ctx(req, env(fakeD1())));
    expect(res.status).toBe(400);
    const body = (await res.json()) as { errors: { kind: string }[] };
    expect(body.errors.some((e) => e.kind === "unknown-handle")).toBe(true);
  });

  it("does not leak another user's story (404)", async () => {
    stubFetch();
    const db = fakeD1();
    const created = await onRequestPost(ctx(postJson(BASE, validBody(), await bearer("user-1")), env(db)));
    const { id } = (await created.json()) as { id: string };

    const intruder = await bearer("user-2");
    const res = await getOne(ctx(new Request(`${BASE}/${id}`, { headers: intruder }), env(db), { id }));
    expect(res.status).toBe(404);
  });
});
