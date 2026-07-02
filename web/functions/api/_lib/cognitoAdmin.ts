// AWS SigV4 signing + Cognito Identity Provider admin API helpers.
// Used by /api/admin/users to list users, manage group memberships, and update
// custom attributes via IAM credentials (COGNITO_ADMIN_ACCESS_KEY_ID /
// COGNITO_ADMIN_SECRET_ACCESS_KEY). Only admin-gated routes call this module;
// JWKS verification for incoming tokens uses the separate _lib/auth.ts path.

const COGNITO_SERVICE = "cognito-idp";

export interface CognitoAdminEnv {
  COGNITO_REGION: string;
  COGNITO_USER_POOL_ID: string;
  COGNITO_ADMIN_ACCESS_KEY_ID: string;
  COGNITO_ADMIN_SECRET_ACCESS_KEY: string;
}

// ---------------------------------------------------------------------------
// Minimal AWS Signature Version 4 — Web Crypto (HMAC-SHA-256)
// ---------------------------------------------------------------------------

async function hmac(key: ArrayBuffer, data: string): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
  ]);
  return crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(data));
}

async function sha256Hex(data: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(data));
  return hex(buf);
}

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function toAmzDate(d: Date): string {
  // Format: 20260629T123456Z (no separators)
  return `${d.toISOString().replace(/[:-]/g, "").slice(0, 15)}Z`;
}

async function authHeader(
  method: string,
  endpoint: URL,
  extraHeaders: Record<string, string>,
  body: string,
  creds: { id: string; secret: string },
  region: string,
  service: string,
  datetime: string,
): Promise<string> {
  const date = datetime.slice(0, 8);

  const allHeaders: Record<string, string> = {
    ...extraHeaders,
    host: endpoint.hostname,
    "x-amz-date": datetime,
  };
  const sortedKeys = Object.keys(allHeaders)
    .map((k) => k.toLowerCase())
    .sort();

  const canonicalHeaders = sortedKeys.map((k) => `${k}:${allHeaders[k]}\n`).join("");
  const signedHeaders = sortedKeys.join(";");

  const payloadHash = await sha256Hex(body);
  const canonicalRequest = [
    method.toUpperCase(),
    endpoint.pathname || "/",
    "",
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");

  const credScope = `${date}/${region}/${service}/aws4_request`;
  const stringToSign = ["AWS4-HMAC-SHA256", datetime, credScope, await sha256Hex(canonicalRequest)].join(
    "\n",
  );

  // Derive signing key
  let key: ArrayBuffer = new TextEncoder().encode(`AWS4${creds.secret}`).buffer as ArrayBuffer;
  for (const piece of [date, region, service, "aws4_request"]) {
    key = await hmac(key, piece);
  }

  const signature = hex(await hmac(key, stringToSign));
  return `AWS4-HMAC-SHA256 Credential=${creds.id}/${credScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;
}

/** Call a Cognito IdP operation and return the parsed JSON response. Throws on HTTP errors. */
async function cognitoPost(
  env: CognitoAdminEnv,
  target: string,
  body: Record<string, unknown>,
): Promise<unknown> {
  const endpoint = new URL(`https://${COGNITO_SERVICE}.${env.COGNITO_REGION}.amazonaws.com/`);
  const bodyStr = JSON.stringify(body);
  const datetime = toAmzDate(new Date());

  const extraHeaders: Record<string, string> = {
    "content-type": "application/x-amz-json-1.1",
    "x-amz-target": `AmazonCognitoIdentityProvider.${target}`,
  };

  const authorization = await authHeader(
    "POST",
    endpoint,
    extraHeaders,
    bodyStr,
    { id: env.COGNITO_ADMIN_ACCESS_KEY_ID, secret: env.COGNITO_ADMIN_SECRET_ACCESS_KEY },
    env.COGNITO_REGION,
    COGNITO_SERVICE,
    datetime,
  );

  const res = await fetch(endpoint.toString(), {
    method: "POST",
    headers: {
      ...extraHeaders,
      host: endpoint.hostname,
      "x-amz-date": datetime,
      authorization,
      "content-length": String(new TextEncoder().encode(bodyStr).length),
    },
    body: bodyStr,
  });

  if (!res.ok) {
    const msg = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(`Cognito ${target} failed (${res.status}): ${msg}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

export interface CognitoUser {
  sub: string;
  email: string;
  groups: string[];
  adminSites: string[];
}

interface RawCognitoUser {
  Username?: string;
  Attributes?: Array<{ Name: string; Value: string }>;
}

function parseUsers(raw: RawCognitoUser[]): Array<{ sub: string; email: string; adminSites: string[] }> {
  return raw.map((u) => {
    const attrs = u.Attributes ?? [];
    const attr = (name: string): string => attrs.find((a) => a.Name === name)?.Value ?? "";
    const adminSitesRaw = attr("custom:admin_sites");
    return {
      sub: attr("sub"),
      email: attr("email"),
      adminSites: adminSitesRaw
        ? adminSitesRaw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    };
  });
}

// ---------------------------------------------------------------------------
// API operations
// ---------------------------------------------------------------------------

/** Fetch a single user's attributes by their `sub`. Returns null if not found. */
export async function getUser(
  env: CognitoAdminEnv,
  sub: string,
): Promise<{ sub: string; email: string; adminSites: string[] } | null> {
  try {
    const res = (await cognitoPost(env, "AdminGetUser", {
      UserPoolId: env.COGNITO_USER_POOL_ID,
      Username: sub,
    })) as { UserAttributes?: Array<{ Name: string; Value: string }> };
    const attrs = res.UserAttributes ?? [];
    const attr = (name: string): string => attrs.find((a) => a.Name === name)?.Value ?? "";
    const adminSitesRaw = attr("custom:admin_sites");
    return {
      sub: attr("sub"),
      email: attr("email"),
      adminSites: adminSitesRaw
        ? adminSitesRaw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    };
  } catch {
    return null;
  }
}

/** List up to 20 users whose email contains `filter`. */
export async function listUsers(
  env: CognitoAdminEnv,
  filter: string,
): Promise<Array<{ sub: string; email: string; adminSites: string[] }>> {
  const filterExpr = filter ? `email ^= "${filter.replace(/"/g, "")}"` : undefined;
  const body: Record<string, unknown> = {
    UserPoolId: env.COGNITO_USER_POOL_ID,
    Limit: 20,
  };
  if (filterExpr) body.Filter = filterExpr;

  const res = (await cognitoPost(env, "ListUsers", body)) as { Users?: RawCognitoUser[] };
  return parseUsers(res.Users ?? []);
}

/** Return the group names for a user (by sub). */
export async function listGroupsForUser(env: CognitoAdminEnv, sub: string): Promise<string[]> {
  const res = (await cognitoPost(env, "AdminListGroupsForUser", {
    UserPoolId: env.COGNITO_USER_POOL_ID,
    Username: sub,
    Limit: 10,
  })) as { Groups?: Array<{ GroupName: string }> };
  return (res.Groups ?? []).map((g) => g.GroupName);
}

/** Replace a user's group memberships with `newGroups`. Throws on error. */
export async function setGroupsForUser(
  env: CognitoAdminEnv,
  sub: string,
  newGroups: string[],
): Promise<void> {
  const current = await listGroupsForUser(env, sub);

  const MANAGED_GROUPS = ["admin", "site-admin", "standard"];
  const toRemove = current.filter((g) => MANAGED_GROUPS.includes(g) && !newGroups.includes(g));
  const toAdd = newGroups.filter((g) => MANAGED_GROUPS.includes(g) && !current.includes(g));

  // Apply removes before adds in sequence — parallel Promise.all can leave a
  // half-applied role set if any call fails, with no clean recovery path.
  for (const g of toRemove) {
    await cognitoPost(env, "AdminRemoveUserFromGroup", {
      UserPoolId: env.COGNITO_USER_POOL_ID,
      Username: sub,
      GroupName: g,
    });
  }
  for (const g of toAdd) {
    await cognitoPost(env, "AdminAddUserToGroup", {
      UserPoolId: env.COGNITO_USER_POOL_ID,
      Username: sub,
      GroupName: g,
    });
  }
}

/** Add a user to a single Cognito group. Idempotent (Cognito ignores if already member). */
export async function addUserToGroup(env: CognitoAdminEnv, sub: string, group: string): Promise<void> {
  await cognitoPost(env, "AdminAddUserToGroup", {
    UserPoolId: env.COGNITO_USER_POOL_ID,
    Username: sub,
    GroupName: group,
  });
}

/** Remove a user from a single Cognito group. Idempotent (Cognito ignores if not member). */
export async function removeUserFromGroup(env: CognitoAdminEnv, sub: string, group: string): Promise<void> {
  await cognitoPost(env, "AdminRemoveUserFromGroup", {
    UserPoolId: env.COGNITO_USER_POOL_ID,
    Username: sub,
    GroupName: group,
  });
}

/** Update the `custom:admin_sites` attribute for a user. */
export async function setAdminSites(env: CognitoAdminEnv, sub: string, sites: string[]): Promise<void> {
  await cognitoPost(env, "AdminUpdateUserAttributes", {
    UserPoolId: env.COGNITO_USER_POOL_ID,
    Username: sub,
    UserAttributes: [{ Name: "custom:admin_sites", Value: sites.join(",") }],
  });
}
