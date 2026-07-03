// Tier A integration test for the /api/stories Pages Functions (functions/api/stories.ts +
// stories/[id].ts): drive the exported handlers end-to-end with a faked Env (a real in-memory D1 +
// a stubbed catalog asset + a minted Cognito token), so the full path — kill switch → auth →
// rate-limit → server-side compile/handle-validation → transactional D1 write — runs offline.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetCatalogCache } from "@fn/api/_lib/catalogAsset";
import type { StoriesEnv } from "@fn/api/_lib/storiesRoute";
import { onRequestGet as adminList, onRequestPost as adminAct } from "@fn/api/admin/stories";
import { onRequestDelete, onRequestGet as getOne, onRequestPut } from "@fn/api/stories/[id]";
import { onRequestPost as postReport } from "@fn/api/stories/report";
import { onRequestGet as getShared } from "@fn/api/stories/shared/[shareId]";
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

// A loose ctx for the public/report/admin handlers. `shareId` satisfies the shared-read handler's
// `params.shareId`; report/admin ignore it.
const anyCtx = (request: Request, e: Record<string, unknown>, shareId = "") => ({
  request,
  env: e as unknown as StoriesEnv,
  params: { shareId },
});

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

describe("/api/stories — publish gate (#1098)", () => {
  it("a standard user can't publish (403) but can save a draft (201)", async () => {
    stubFetch();
    const db = fakeD1();
    const pub = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "published" }), await bearer()), env(db)),
    );
    expect(pub.status).toBe(403);
    const draft = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "draft" }), await bearer()), env(db)),
    );
    expect(draft.status).toBe(201);
    expect(((await draft.json()) as { share_id: string | null }).share_id).toBeNull();
  });

  it("an early-access user publishes and receives a share_id", async () => {
    stubFetch();
    const db = fakeD1();
    const res = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "published" }), await bearer("u", ["early-access"])), env(db)),
    );
    expect(res.status).toBe(201);
    expect(((await res.json()) as { share_id: string | null }).share_id).toBeTruthy();
  });
});

describe("/api/stories/shared/:shareId — public read (#1098)", () => {
  it("serves a published story to an unauthenticated visitor; a bogus id 404s", async () => {
    stubFetch();
    const db = fakeD1();
    const created = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "published" }), await bearer("u", ["early-access"])), env(db)),
    );
    const { share_id } = (await created.json()) as { share_id: string };

    // NO auth header on the public read.
    const pub = await getShared(anyCtx(new Request(`${BASE}/shared/${share_id}`), env(db), share_id));
    expect(pub.status).toBe(200);
    const detail = (await pub.json()) as { story: { title: string; refs: unknown[] } };
    expect(detail.story.title).toBe("My Story");
    expect(detail.story.refs.length).toBe(1);

    const miss = await getShared(anyCtx(new Request(`${BASE}/shared/nope`), env(db), "nope"));
    expect(miss.status).toBe(404);
  });

  it("an unpublished story is no longer reachable by its old share id", async () => {
    stubFetch();
    const db = fakeD1();
    const created = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "published" }), await bearer("u", ["early-access"])), env(db)),
    );
    const { id, share_id } = (await created.json()) as { id: string; share_id: string };
    const put = new Request(`${BASE}/${id}`, {
      method: "PUT",
      headers: { "content-type": "application/json", ...(await bearer("u", ["early-access"])) },
      body: JSON.stringify(validBody({ status: "draft" })),
    });
    await onRequestPut(ctx(put, env(db), { id }));
    const pub = await getShared(anyCtx(new Request(`${BASE}/shared/${share_id}`), env(db), share_id));
    expect(pub.status).toBe(404);
  });
});

describe("/api/stories/report — public report (#1098)", () => {
  it("accepts a valid report (202) and rejects an invalid reason (400)", async () => {
    stubFetch();
    const db = fakeD1();
    const created = await onRequestPost(
      ctx(postJson(BASE, validBody({ status: "published" }), await bearer("u", ["early-access"])), env(db)),
    );
    const { share_id } = (await created.json()) as { share_id: string };

    const ok = await postReport(
      anyCtx(postJson(`${BASE}/report`, { shareId: share_id, reason: "abuse", detail: "bad" }), env(db)),
    );
    expect(ok.status).toBe(202);
    const bad = await postReport(
      anyCtx(postJson(`${BASE}/report`, { shareId: share_id, reason: "nonsense" }), env(db)),
    );
    expect(bad.status).toBe(400);
  });
});

describe("/api/admin/stories — moderation (#1098)", () => {
  it("forbids non-admins, lists reports, and takes a story down for the public", async () => {
    stubFetch();
    const db = fakeD1();
    const created = await onRequestPost(
      ctx(
        postJson(BASE, validBody({ status: "published" }), await bearer("author", ["early-access"])),
        env(db),
      ),
    );
    const { id, share_id } = (await created.json()) as { id: string; share_id: string };
    await postReport(anyCtx(postJson(`${BASE}/report`, { shareId: share_id, reason: "abuse" }), env(db)));

    const ADMIN = "https://bosc.test/api/admin/stories";
    // early-access is not admin
    const forbidden = await adminList(
      anyCtx(new Request(ADMIN, { headers: await bearer("author", ["early-access"]) }), env(db)),
    );
    expect(forbidden.status).toBe(403);

    // admin sees the report
    const list = await adminList(
      anyCtx(new Request(ADMIN, { headers: await bearer("admin-1", ["admin"]) }), env(db)),
    );
    expect(list.status).toBe(200);
    expect(((await list.json()) as { reports: unknown[] }).reports.length).toBe(1);

    // admin takedown → the public read 404s
    const act = await adminAct(
      anyCtx(postJson(ADMIN, { action: "takedown", id }, await bearer("admin-1", ["admin"])), env(db)),
    );
    expect(act.status).toBe(200);
    const pub = await getShared(anyCtx(new Request(`${BASE}/shared/${share_id}`), env(db), share_id));
    expect(pub.status).toBe(404);
  });
});
