// Tier A integration test for the /api/submit Pages Function (functions/api/submit.ts):
// drive the exported `onRequestPost` end-to-end with a faked Env + a stubbed `fetch`, so
// the full request path (kill switch → validate → rate-limit → Turnstile → GitHub-App JWT
// → dedupe → file issue → private contact store) is exercised offline, no wrangler, no
// network, no real issues filed. Pure `_lib` logic is unit-tested separately
// (submitContact.test.ts et al.); this covers the wiring those leave out.

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { dedupeInput, submissionMarker } from "@watermark/functions/api/_lib/issue";
import { windowKey } from "@watermark/functions/api/_lib/ratelimit";
import { onRequestPost } from "@watermark/functions/api/submit";
import {
  type CognitoTestKeyPair,
  type FetchRoute,
  fakeKV,
  generateCognitoKeyPair,
  generatePkcs8Pem,
  jsonResponse,
  mintIdToken,
  postJson,
  routingFetch,
} from "./_routeHarness";

const SUBMIT_URL = "https://bosc.test/api/submit";
const GITHUB_API_BASE = "https://gh.test"; // exercises the GITHUB_API_BASE seam
const ISSUE_URL = "https://github.com/watermark-directory/the-watermark-directory/issues/123";

let privateKey: string;
beforeAll(async () => {
  privateKey = await generatePkcs8Pem();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function submitEnv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    SUBMISSIONS_ENABLED: "true",
    TURNSTILE_SECRET_KEY: "1x0000000000000000000000000000000AA",
    TIPS_APP_ID: "12345",
    TIPS_APP_PRIVATE_KEY: privateKey,
    GITHUB_OWNER: "watermark-directory",
    GITHUB_REPO: "the-watermark-directory",
    GITHUB_API_BASE,
    ...overrides,
  };
}

const validSubmission = (extra: Record<string, unknown> = {}) => ({
  kind: "tip",
  body: "A culvert behind the plant discharges into the creek after rain.",
  turnstile_token: "tok",
  ...extra,
});

const turnstileRoute = (success: boolean): FetchRoute => ({
  test: (url) => url.pathname === "/turnstile/v0/siteverify",
  respond: () => jsonResponse(200, { success }),
});

// GitHub App auth + issue routes. `issuesOnGet` lets a test seed an existing open
// submission (the dedupe path); default is "no open submissions".
function githubRoutes(issuesOnGet: Array<{ html_url: string; body: string }> = []): FetchRoute[] {
  return [
    {
      test: (url) => url.pathname.endsWith("/installation"),
      respond: () => jsonResponse(200, { id: 42 }),
    },
    {
      test: (url) => url.pathname.endsWith("/access_tokens"),
      respond: () => jsonResponse(201, { token: "ghs_test" }),
    },
    {
      test: (url, m) => url.pathname.endsWith("/issues") && m === "GET",
      respond: () => jsonResponse(200, issuesOnGet),
    },
    {
      test: (url, m) => url.pathname.endsWith("/issues") && m === "POST",
      respond: () => jsonResponse(201, { html_url: ISSUE_URL }),
    },
    {
      // POST /issues/:num/comments — dedupe attachment comment (#243)
      test: (url, m) => /\/issues\/\d+\/comments$/.test(url.pathname) && m === "POST",
      respond: () => jsonResponse(201, { id: 999 }),
    },
  ];
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

describe("/api/submit route", () => {
  it("503s when the kill switch is off", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({ request: postJson(SUBMIT_URL, validSubmission()), env: {} } as never);
    expect(res.status).toBe(503);
  });

  it("500s when secrets are missing", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: { SUBMISSIONS_ENABLED: "true" },
    } as never);
    expect(res.status).toBe(500);
  });

  it("400s on invalid JSON before any external call", async () => {
    const fetchStub = routingFetch([]);
    vi.stubGlobal("fetch", fetchStub);
    const request = new Request(SUBMIT_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{ not json",
    });
    const res = await onRequestPost({ request, env: submitEnv() } as never);
    expect(res.status).toBe(400);
    expect(fetchStub.calls).toHaveLength(0);
  });

  it("400s when the payload fails allowlist validation", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, { kind: "tip" }), // no body, no token
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(400);
  });

  it("403s and never reaches GitHub when Turnstile fails", async () => {
    const fetchStub = routingFetch([turnstileRoute(false), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(403);
    expect(fetchStub.calls.some((c) => c.url.includes("/installation"))).toBe(false);
  });

  it("files an issue and returns 201 on the happy path (honoring GITHUB_API_BASE)", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({ issue_url: ISSUE_URL, deduped: false });
    expect(
      fetchStub.calls.some((c) => c.url.startsWith(GITHUB_API_BASE) && c.url.endsWith("/installation")),
    ).toBe(true);
  });

  it("dedupes against an open submission carrying the same marker (200, no new issue)", async () => {
    const submission = validSubmission();
    const hash = await sha256Hex(dedupeInput(submission as never));
    const existing = {
      html_url: "https://github.com/watermark-directory/the-watermark-directory/issues/7",
      body: `x ${submissionMarker(hash)} y`,
    };
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes([existing])]);
    vi.stubGlobal("fetch", fetchStub);

    const res = await onRequestPost({ request: postJson(SUBMIT_URL, submission), env: submitEnv() } as never);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ issue_url: existing.html_url, deduped: true });
    // The POST that would open a *new* issue must not have fired.
    expect(fetchStub.calls.some((c) => c.method === "POST" && c.url.endsWith("/issues"))).toBe(false);
  });

  it("drops a foreign-origin page_url (keeps a same-origin one)", async () => {
    const issuePost = (stub: ReturnType<typeof routingFetch>) =>
      stub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));

    const foreign = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", foreign);
    await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ page_url: "https://evil.test/phish" })),
      env: submitEnv(),
    } as never);
    expect(issuePost(foreign)?.body).not.toContain("evil.test");
    expect(issuePost(foreign)?.body).not.toContain("From page");
    vi.unstubAllGlobals();

    const same = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", same);
    await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ page_url: "https://bosc.test/network/x" })),
      env: submitEnv(),
    } as never);
    expect(issuePost(same)?.body).toContain("https://bosc.test/network/x");
  });

  it("429s (before Turnstile) when the per-IP window is exhausted", async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const ip = "203.0.113.9";
    const kv = fakeKV({ [windowKey(ip, Math.floor(fixedMs / 1000), 3600)]: "5" }); // default max = 5
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);

    const request = postJson(SUBMIT_URL, validSubmission(), { "CF-Connecting-IP": ip });
    const res = await onRequestPost({ request, env: submitEnv({ RATE_LIMIT: kv }) } as never);
    expect(res.status).toBe(429);
    expect(res.headers.get("Retry-After")).toBeTruthy();
    expect(fetchStub.calls.some((c) => c.url.includes("/siteverify"))).toBe(false);
  });

  it('treats RATE_LIMIT_MAX="0" as block-all (not the default 5) (#588)', async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const ip = "203.0.113.10";
    const kv = fakeKV({}); // no prior submissions
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);

    const request = postJson(SUBMIT_URL, validSubmission(), { "CF-Connecting-IP": ip });
    const res = await onRequestPost({
      request,
      env: submitEnv({ RATE_LIMIT: kv, RATE_LIMIT_MAX: "0" }),
    } as never);
    expect(res.status).toBe(429); // 0 allowed ⇒ first submission already over
    expect(fetchStub.calls.some((c) => c.url.includes("/siteverify"))).toBe(false);
  });

  it("stores submitter contact in the private KV, never in the public issue", async () => {
    const kv = fakeKV();
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);

    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ contact: "tipster@example.com" })),
      env: submitEnv({ SUBMISSION_CONTACT: kv }),
    } as never);
    expect(res.status).toBe(201);

    const stored = kv.store.get("contact:123"); // issue number parsed from ISSUE_URL
    expect(stored).toBeTruthy();
    expect(JSON.parse(stored as string).contact).toBe("tipster@example.com");
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    expect(issuePost?.body).not.toContain("tipster@example.com");
  });

  it("files normally when no contact KV is bound (contact silently skipped)", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ contact: "tipster@example.com" })),
      env: submitEnv(), // no SUBMISSION_CONTACT binding
    } as never);
    expect(res.status).toBe(201);
  });

  // --- #592: previously-untested failure branches -----------------------------------------
  it("502s when the GitHub issue create fails", async () => {
    // installation + token mint succeed, the dedupe scan finds nothing, the create POST 500s.
    const failingCreate: FetchRoute[] = [
      { test: (url) => url.pathname.endsWith("/installation"), respond: () => jsonResponse(200, { id: 42 }) },
      {
        test: (url) => url.pathname.endsWith("/access_tokens"),
        respond: () => jsonResponse(201, { token: "ghs_test" }),
      },
      {
        test: (url, m) => url.pathname.endsWith("/issues") && m === "GET",
        respond: () => jsonResponse(200, []),
      },
      {
        test: (url, m) => url.pathname.endsWith("/issues") && m === "POST",
        respond: () => jsonResponse(500, { message: "GitHub is down" }),
      },
    ];
    const fetchStub = routingFetch([turnstileRoute(true), ...failingCreate]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(502);
  });

  it("still returns 201 when the contact-store put fails (the tip is what matters)", async () => {
    // A KV whose put rejects — the submission must not fail; contact is best-effort.
    const flakyContact = {
      get: async () => null,
      put: async () => {
        throw new Error("contact KV unavailable");
      },
    };
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ contact: "tipster@example.com" })),
      env: submitEnv({ SUBMISSION_CONTACT: flakyContact }),
    } as never);
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual({ issue_url: ISSUE_URL, deduped: false });
  });
});

// ---------------------------------------------------------------------------
// Auth gate tests (Epic #920 B3)
// ---------------------------------------------------------------------------

describe("/api/submit — auth gate (AUTH_ENABLED=true)", () => {
  let cognitoKey: CognitoTestKeyPair;
  beforeAll(async () => {
    cognitoKey = await generateCognitoKeyPair();
  });

  const TEST_REGION = "us-east-1";
  const TEST_POOL_ID = "us-east-1_TEST";
  const TEST_CLIENT_ID = "test-client-id";

  function authEnv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return submitEnv({
      AUTH_ENABLED: "true",
      COGNITO_REGION: TEST_REGION,
      COGNITO_USER_POOL_ID: TEST_POOL_ID,
      COGNITO_CLIENT_ID: TEST_CLIENT_ID,
      ...overrides,
    });
  }

  const jwksRoute = (): FetchRoute => ({
    test: (url) => url.pathname.endsWith("/.well-known/jwks.json"),
    respond: () => jsonResponse(200, { keys: [cognitoKey.jwk] }),
  });

  it("401s when no Authorization header is present", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: authEnv(),
    } as never);
    expect(res.status).toBe(401);
  });

  it("401s when an invalid Bearer token is provided", async () => {
    vi.stubGlobal("fetch", routingFetch([jwksRoute()]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission(), { Authorization: "Bearer not.a.real.token" }),
      env: authEnv(),
    } as never);
    expect(res.status).toBe(401);
  });

  it("401s when the Bearer token is signed with the wrong key", async () => {
    const wrongKey = await generateCognitoKeyPair();
    const token = await mintIdToken(wrongKey, {
      sub: "user-sub",
      email: "user@example.com",
      clientId: TEST_CLIENT_ID,
      userPoolId: TEST_POOL_ID,
      region: TEST_REGION,
    });
    vi.stubGlobal("fetch", routingFetch([jwksRoute()])); // JWKS has cognitoKey, not wrongKey
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission(), { Authorization: `Bearer ${token}` }),
      env: authEnv(),
    } as never);
    expect(res.status).toBe(401);
  });

  it("500s when AUTH_ENABLED=true but COGNITO vars are absent", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv({ AUTH_ENABLED: "true" }), // no COGNITO_* vars
    } as never);
    expect(res.status).toBe(500);
  });

  it("files issue with sub attribution when a valid Bearer token is provided", async () => {
    const token = await mintIdToken(cognitoKey, {
      sub: "user-sub-abc123",
      email: "tipster@example.com",
      clientId: TEST_CLIENT_ID,
      userPoolId: TEST_POOL_ID,
      region: TEST_REGION,
    });
    const fetchStub = routingFetch([jwksRoute(), turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission(), { Authorization: `Bearer ${token}` }),
      env: authEnv(),
    } as never);
    expect(res.status).toBe(201);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    expect(issuePost?.body).toContain("user-sub-abc123");
  });

  it("existing tests are unaffected when AUTH_ENABLED is absent (backward compat)", async () => {
    // submitEnv() does not set AUTH_ENABLED — the gate must be bypassed entirely.
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv(), // no auth vars
    } as never);
    expect(res.status).toBe(201);
  });
});

// ---------------------------------------------------------------------------
// Notify-on-submit tests (#244)
// ---------------------------------------------------------------------------

describe("/api/submit — NOTIFY_GITHUB_USERS (#244)", () => {
  it("includes assignees in the issue create body when NOTIFY_GITHUB_USERS is set", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv({ NOTIFY_GITHUB_USERS: "goedelsoup" }),
    } as never);
    expect(res.status).toBe(201);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    const body = JSON.parse(issuePost?.body ?? "{}") as { assignees?: string[] };
    expect(body.assignees).toEqual(["goedelsoup"]);
  });

  it("supports multiple assignees (comma-separated)", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv({ NOTIFY_GITHUB_USERS: "alice, bob, carol" }),
    } as never);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    const body = JSON.parse(issuePost?.body ?? "{}") as { assignees?: string[] };
    expect(body.assignees).toEqual(["alice", "bob", "carol"]);
  });

  it("does not set assignees when NOTIFY_GITHUB_USERS is absent", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission()),
      env: submitEnv(), // no NOTIFY_GITHUB_USERS
    } as never);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    const body = JSON.parse(issuePost?.body ?? "{}") as { assignees?: string[] };
    // assignees should be absent or empty (github.ts only sets it when non-empty)
    expect(body.assignees == null || body.assignees.length === 0).toBe(true);
  });

  it("does not assign on deduped submissions (no new issue opened)", async () => {
    const submission = validSubmission();
    const hash = await sha256Hex(`\n${String(submission.body).trim().toLowerCase()}`);
    const marker = `<!-- submission: ${hash} -->`;
    const existing = [{ html_url: ISSUE_URL, body: marker }];
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes(existing)]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, submission),
      env: submitEnv({ NOTIFY_GITHUB_USERS: "goedelsoup" }),
    } as never);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { deduped?: boolean };
    expect(body.deduped).toBe(true);
    // No POST /issues call — dedupe returned early
    const issuePosts = fetchStub.calls.filter((c) => c.method === "POST" && c.url.endsWith("/issues"));
    expect(issuePosts.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// File attachment tests (#243)
// ---------------------------------------------------------------------------

describe("/api/submit — attachment_keys (#243)", () => {
  // Minimal fake R2 for the submit endpoint's head() validation calls.
  function fakeAttachR2(storedKeys: string[] = []) {
    const stored = new Set(storedKeys);
    return {
      put: async () => undefined,
      head: async (key: string) => (stored.has(key) ? { size: 1234 } : null),
    };
  }

  it("rejects attachment_keys with invalid prefix", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ attachment_keys: ["evil/path/file.pdf"] })),
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(400);
  });

  it("rejects more than 3 attachment_keys", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: postJson(
        SUBMIT_URL,
        validSubmission({
          attachment_keys: [
            "submissions/2026-06-29/a/1.pdf",
            "submissions/2026-06-29/b/2.pdf",
            "submissions/2026-06-29/c/3.pdf",
            "submissions/2026-06-29/d/4.pdf",
          ],
        }),
      ),
      env: submitEnv(),
    } as never);
    expect(res.status).toBe(400);
  });

  it("includes verified attachment keys in the issue body", async () => {
    const key = "submissions/2026-06-29/abc/report.pdf";
    const r2 = fakeAttachR2([key]);
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ attachment_keys: [key] })),
      env: submitEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(201);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    expect(issuePost?.body).toContain(key);
    expect(issuePost?.body).toContain("Attachments");
  });

  it("silently drops attachment keys that don't exist in R2", async () => {
    const key = "submissions/2026-06-29/ghost/missing.pdf";
    const r2 = fakeAttachR2([]); // key not stored
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ attachment_keys: [key] })),
      env: submitEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    // Submission should still succeed
    expect(res.status).toBe(201);
    const issuePost = fetchStub.calls.find((c) => c.method === "POST" && c.url.endsWith("/issues"));
    expect(issuePost?.body).not.toContain("Attachments");
  });

  it("files successfully when SUBMISSION_ATTACHMENTS is absent (attachment_keys silently dropped)", async () => {
    const key = "submissions/2026-06-29/abc/file.pdf";
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes()]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ attachment_keys: [key] })),
      env: submitEnv(), // no SUBMISSION_ATTACHMENTS
    } as never);
    expect(res.status).toBe(201);
  });

  it("comments attachment keys on the existing issue when a dedupe hits with attachments (#243)", async () => {
    const key = "submissions/2026-06-29/abc/report.pdf";
    const r2 = fakeAttachR2([key]);
    const base = validSubmission();
    const hash = await sha256Hex(dedupeInput(base as never));
    const existing = {
      html_url: "https://github.com/watermark-directory/the-watermark-directory/issues/7",
      body: `x ${submissionMarker(hash)} y`,
    };
    const fetchStub = routingFetch([turnstileRoute(true), ...githubRoutes([existing])]);
    vi.stubGlobal("fetch", fetchStub);

    const res = await onRequestPost({
      request: postJson(SUBMIT_URL, validSubmission({ attachment_keys: [key] })),
      env: submitEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { deduped?: boolean };
    expect(body.deduped).toBe(true);

    // A comment carrying the attachment key must have been posted on issue #7
    const commentPost = fetchStub.calls.find(
      (c) => c.method === "POST" && /\/issues\/7\/comments$/.test(new URL(c.url).pathname),
    );
    expect(commentPost).toBeTruthy();
    expect(commentPost?.body).toContain(key);
  });
});
