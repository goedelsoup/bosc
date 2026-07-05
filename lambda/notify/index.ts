// Lambda handler: GitHub webhook → Lakebase subscriber lookup → SES email dispatch (#938 E1).
//
// Triggered by an API Gateway (Lambda URL) receiving `issues.opened` events from the
// GitHub webhook on the `watermark-directory/the-watermark-directory` repository.
//
// Flow:
//   1. Verify the GitHub webhook signature (X-Hub-Signature-256).
//   2. Parse the issue labels to determine notification category.
//   3. Enumerate subscribers from the `user_prefs` table in Databricks Lakebase (managed
//      Postgres) matching the category + a site that matches the issue's site label.
//   4. Send an immediate SES email for each `immediate`-frequency subscriber.
//   5. Increment the `user_prefs.digest_pending` counter for `daily` subscribers
//      (flushed by a separate EventBridge-triggered digest Lambda, future work).
//
// Subscriber prefs moved off Cloudflare KV onto Lakebase in #1171 (Worker side) / #1206 (this
// Lambda). Because the Lambda runs in AWS — outside the Workers runtime — it can't use the
// `AUTH_HYPERDRIVE` binding the Pages Functions use; it opens its own direct Postgres connection.
// The `notif_sites` / `notif_categories` columns are JSON-encoded TEXT (mirroring the store), not
// Postgres arrays — parsed here the same way `web/functions/api/_lib/authStore.ts` does.
//
// Required environment variables (set in Lambda console / Pulumi secrets):
//   GITHUB_WEBHOOK_SECRET       — shared secret used to verify X-Hub-Signature-256
//   LAKEBASE_URL                — postgres:// connection string to Lakebase (same secret Stories uses)
//   SES_FROM_ADDRESS            — verified SES sender address
//   SITE_URL                    — base URL for unsubscribe links (e.g. https://watermarkdirectory.org)
//   UNSUB_SECRET                — shared HMAC secret (same as Pages Function UNSUB_SECRET)

import {
  type APIGatewayProxyEventV2,
  type APIGatewayProxyResultV2,
  type ScheduledEvent,
} from "aws-lambda";
import { createHmac, timingSafeEqual } from "crypto";
import { SESClient, SendEmailCommand } from "@aws-sdk/client-ses";
import postgres, { type Sql } from "postgres";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IssueEvent {
  action: string;
  issue: {
    number: number;
    title: string;
    html_url: string;
    labels: Array<{ name: string }>;
  };
  repository: {
    full_name: string;
  };
}

// One `user_prefs` row joined with the subscriber's last-seen email from `users`. The site/category
// lists are JSON-encoded TEXT (parsed below), `email` is nullable (unsubscribe rows carry no email,
// and it's a non-authoritative last-seen value — the live Cognito claim wins when a send is wired).
interface SubscriberRow {
  sub: string;
  notif_sites: string;
  notif_categories: string;
  notif_frequency: string;
  email: string | null;
}

type NotifCategory = "tip" | "correction" | "new_source" | "hypothesis";

const CATEGORY_LABELS: Record<string, NotifCategory> = {
  "[tip]": "tip",
  "[correction]": "correction",
  "[new-source]": "new_source",
  hypothesis: "hypothesis",
};

// ---------------------------------------------------------------------------
// GitHub webhook signature verification
// ---------------------------------------------------------------------------

function verifySignature(secret: string, body: string, signature: string): boolean {
  const expected = `sha256=${createHmac("sha256", secret).update(body).digest("hex")}`;
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Lakebase (Postgres) client
// ---------------------------------------------------------------------------

// Memoized per connection string: a warm Lambda container reuses the module-global client across
// invocations rather than reconnecting per webhook. `ssl: "require"` — Lakebase (managed Postgres)
// only accepts TLS connections. Unlike the Worker-side `pg.ts`, there's no Hyperdrive in front, so
// this is a direct pooled connection (`max: 1` — a Lambda container serves one request at a time).
let cached: { key: string; sql: Sql } | undefined;

function lakebase(connectionString: string): Sql {
  if (cached?.key === connectionString) return cached.sql;
  const sql = postgres(connectionString, { max: 1, ssl: "require" });
  cached = { key: connectionString, sql };
  return sql;
}

/** Parse a JSON-array TEXT column back to a string[]; tolerates malformed/non-array values.
 *  Mirrors `parseStringArray` in `web/functions/api/_lib/authStore.ts` (same stored shape). */
function parseStringArray(raw: string): string[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Unsubscribe token (mirrors _lib/unsub.ts for the Lambda side)
// ---------------------------------------------------------------------------

const TOKEN_TTL_SEC = 30 * 24 * 60 * 60;

function base64urlEncode(buf: Buffer): string {
  return buf.toString("base64url");
}

function base64urlEncodeStr(s: string): string {
  return base64urlEncode(Buffer.from(s, "utf8"));
}

function signUnsubToken(sub: string, category: string, secret: string): string {
  const exp = Math.floor(Date.now() / 1000) + TOKEN_TTL_SEC;
  const message = `${sub}|${category}|${exp}`;
  const sig = createHmac("sha256", secret).update(message).digest("base64url");
  return [base64urlEncodeStr(sub), base64urlEncodeStr(category), String(exp), sig].join(".");
}

// ---------------------------------------------------------------------------
// SES email dispatch
// ---------------------------------------------------------------------------

const ses = new SESClient({});

async function sendNotificationEmail(params: {
  toEmail: string;
  sub: string;
  category: string;
  issue: IssueEvent["issue"];
  siteUrl: string;
  unsubSecret: string;
  fromAddress: string;
}): Promise<void> {
  const { toEmail, sub, category, issue, siteUrl, unsubSecret, fromAddress } = params;
  const unsubToken = signUnsubToken(sub, category, unsubSecret);
  const unsubUrl = `${siteUrl}/account/unsubscribe?token=${unsubToken}`;

  const categoryLabel: Record<string, string> = {
    tip: "New tip",
    correction: "Correction submitted",
    new_source: "New source added",
    hypothesis: "Hypothesis update",
  };

  const subject = `[Watermark] ${categoryLabel[category] ?? "Update"}: ${issue.title}`;

  const body = `A new ${category.replace("_", " ")} has been posted to the Watermark Directory.

Issue: ${issue.title}
Link: ${issue.html_url}

---
To stop receiving these emails, click: ${unsubUrl}
To manage all notification preferences, visit: ${siteUrl}/account
`;

  await ses.send(
    new SendEmailCommand({
      Source: fromAddress,
      Destination: { ToAddresses: [toEmail] },
      Message: {
        Subject: { Data: subject, Charset: "UTF-8" },
        Body: { Text: { Data: body, Charset: "UTF-8" } },
      },
    }),
  );
}

// ---------------------------------------------------------------------------
// Main handler (webhook + scheduled digest trigger stub)
// ---------------------------------------------------------------------------

export const handler = async (
  event: APIGatewayProxyEventV2 | ScheduledEvent,
): Promise<APIGatewayProxyResultV2 | void> => {
  const env = {
    GITHUB_WEBHOOK_SECRET: process.env.GITHUB_WEBHOOK_SECRET ?? "",
    LAKEBASE_URL: process.env.LAKEBASE_URL ?? "",
    SES_FROM_ADDRESS: process.env.SES_FROM_ADDRESS ?? "",
    SITE_URL: process.env.SITE_URL ?? "",
    UNSUB_SECRET: process.env.UNSUB_SECRET ?? "",
  };

  // EventBridge scheduled event — daily digest flush (stubbed; TODO: #938 follow-up).
  if ("source" in event && event.source === "aws.events") {
    console.log("Daily digest trigger received — digest dispatch not yet implemented.");
    return;
  }

  // Fail closed: all required env vars must be present before touching secrets.
  const missing = Object.entries(env)
    .filter(([, value]) => !value)
    .map(([key]) => key);
  if (missing.length) {
    console.error("Notify Lambda missing required env vars", missing);
    return { statusCode: 500, body: "notification service misconfigured" };
  }

  // API Gateway webhook event.
  const webhookEvent = event as APIGatewayProxyEventV2;
  const body = webhookEvent.body ?? "";
  const ghEvent = webhookEvent.headers?.["x-github-event"];
  const signature = webhookEvent.headers?.["x-hub-signature-256"] ?? "";

  if (!verifySignature(env.GITHUB_WEBHOOK_SECRET, body, signature)) {
    return { statusCode: 401, body: "invalid signature" };
  }

  if (ghEvent !== "issues") {
    return { statusCode: 200, body: "ignored" };
  }

  let parsed: IssueEvent;
  try {
    parsed = JSON.parse(body) as IssueEvent;
  } catch {
    return { statusCode: 400, body: "invalid JSON" };
  }

  if (parsed.action !== "opened") {
    return { statusCode: 200, body: "ignored" };
  }

  const labelNames = parsed.issue.labels.map((l) => l.name);

  // Determine notification category from labels.
  const category = Object.entries(CATEGORY_LABELS).find(([label]) =>
    labelNames.includes(label),
  )?.[1];

  // Determine site from a `site:<slug>` label.
  const siteSlug = labelNames.find((l) => l.startsWith("site:"))?.slice(5) ?? null;

  if (!category) {
    return { statusCode: 200, body: "no matching category label" };
  }
  if (!siteSlug) {
    return { statusCode: 200, body: "no matching site label" };
  }

  // Enumerate subscribers from Lakebase. The KV keyspace scan (`prefs:*`) becomes a single
  // `SELECT` over `user_prefs`, left-joined to `users` for the last-seen email. Category/site
  // filtering stays in code (the lists are JSON-encoded TEXT, parsed like the store does) —
  // subscriber volume is small, so a full read + in-memory filter mirrors the old KV behavior.
  const sql = lakebase(env.LAKEBASE_URL);
  const rows = await sql<SubscriberRow[]>`
    SELECT p.sub, p.notif_sites, p.notif_categories, p.notif_frequency, u.email
    FROM user_prefs p
    LEFT JOIN users u ON u.sub = p.sub
  `;

  let sent = 0;
  let digest = 0;

  for (const row of rows) {
    const categories = parseStringArray(row.notif_categories);
    const sites = parseStringArray(row.notif_sites);

    // Check category subscription.
    if (!categories.includes(category)) continue;

    // Check site subscription (an empty site list means "all sites").
    if (siteSlug && sites.length && !sites.includes(siteSlug)) continue;

    const sub = row.sub;

    if (row.notif_frequency === "daily") {
      // Increment the pending-digest counter (flushed by the scheduled Lambda, #938 follow-up).
      // Best-effort: a failure here must not abort the rest of the fan-out.
      await sql`
        UPDATE user_prefs SET digest_pending = digest_pending + 1 WHERE sub = ${sub}
      `.catch((e: unknown) => console.error("digest increment failed", sub, e));
      digest++;
      continue;
    }

    // Immediate dispatch. `users.email` is a non-authoritative last-seen value and `email_verified`
    // is a live Cognito claim not stored in Postgres — so the actual SES send (with an AdminGetUser
    // verification check) is still the #938 follow-up. Until then, log and skip without counting as
    // sent. The address is now sourced here so wiring the send is a local change.
    console.log(
      `TODO: send immediate email to sub=${sub} category=${category} email=${row.email ?? "unknown"}`,
    );
  }

  console.log(`Dispatched: ${sent} immediate, ${digest} queued for digest`);
  return { statusCode: 200, body: JSON.stringify({ sent, digest }) };
};
