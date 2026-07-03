import * as fs from "node:fs";
import * as path from "node:path";
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as cloudflare from "@pulumi/cloudflare";
import * as yaml from "js-yaml";

// ---------------------------------------------------------------------------
// Deployment infrastructure for the Watermark Directory (Epic #56 / #240)
// ---------------------------------------------------------------------------
// A dedicated Pulumi stack, separate from the GitHub repo-config stack
// (../.github/config): different providers + credentials, lifecycle, blast radius.
//
// It owns the deploy-independent resources the public submissions endpoint (#74)
// depends on, plus the auth layer (#919/#924), and — when a custom domain is set —
// the AWS↔Cloudflare exchange that puts the Pages site on a Route53-hosted name:
//
//   • PagesProject env vars     — feature toggles (features.yaml) + all secrets +
//                                 Cognito IDs written directly to the project config.
//   • Workers KV namespaces     — rate limiter, contact store, auth caches.
//   • Hyperdrive config         — pooled Postgres path to Lakebase for user Stories
//                                 (#1090); gated on features.stories.
//   • R2 bucket                 — submission file attachments (#243).
//   • Turnstile widget          — guards the public form.
//   • Cognito User Pool         — auth identity (#924); gated on `authEnabled`.
//   • Pages custom domain       — attaches `siteDomain` to the wrangler-deployed
//                                 Pages project (the Cloudflare side).
//   • Route53 CNAME             — points `siteDomain` at `<project>.pages.dev`
//                                 (the AWS side); Cloudflare validates via it and
//                                 issues the edge cert.
//
// The Pages project itself (code + bindings) is deployed by wrangler
// (../.github/workflows/pages.yml / ../web/wrangler.toml). Pulumi manages the
// project-level env var config via `PagesProject`; wrangler manages deployments.
// The two don't conflict: wrangler `pages deploy` pushes code/assets; Pulumi owns
// project settings. KV bindings + R2 bindings remain in wrangler.toml because the
// binding IDs are written there after `pulumi up` (a future improvement could move
// them here too).
//
// First apply on an existing project: import it first so Pulumi doesn't try to
// recreate it:
//   pulumi import cloudflare:index/pagesProject:PagesProject site-project \
//     <accountId>/<projectName>
//
// State + auth (see README):
//   • Backend  — self-managed **S3** (`pulumi login s3://…`); secrets via **awskms**.
//   • Cloudflare — default provider reads `CLOUDFLARE_API_TOKEN` (KV + Turnstile +
//     Pages-domain + R2 edit + PagesProject).
//   • AWS — standard credential chain (env / OIDC role); used for Route53 (when
//     `siteDomain` + `route53ZoneId` are set) and Cognito (when `authEnabled`).

const config = new pulumi.Config();

// ---------------------------------------------------------------------------
// features.yaml — committed feature kill switches applied by `pulumi up`
// ---------------------------------------------------------------------------
interface Features {
    preLaunch: boolean;
    submissions: boolean;
    ask: boolean;
    docs: boolean;
    mcp: boolean;
    rum: boolean;
    auth: boolean;
    stories: boolean;
}
function validateFeatures(raw: unknown): Features {
    if (typeof raw !== "object" || raw === null) {
        throw new Error("features.yaml must be a YAML mapping");
    }
    const obj = raw as Record<string, unknown>;
    const keys: (keyof Features)[] = ["preLaunch", "submissions", "ask", "docs", "mcp", "rum", "auth", "stories"];
    for (const key of keys) {
        if (typeof obj[key] !== "boolean") {
            throw new Error(
                `features.yaml: "${key}" must be a boolean (true or false), got ${JSON.stringify(obj[key])}`,
            );
        }
    }
    return obj as unknown as Features;
}
const features = validateFeatures(
    yaml.load(fs.readFileSync(path.join(__dirname, "features.yaml"), "utf8")),
);

// ---------------------------------------------------------------------------
// Secrets — set out of band via `pulumi config set --secret bosc-deploy:<key>`
// ---------------------------------------------------------------------------
// These are written as secret_text env vars to the Pages project by `pulumi up`,
// replacing manual dashboard steps. Each is optional so `pulumi up` doesn't fail
// before the secret is provisioned; missing vars are simply omitted from Pages.
//   pulumi config set --secret bosc-deploy:anthropicApiKey   <key>
//   pulumi config set --secret bosc-deploy:honeycombApiKey   <key>
//   pulumi config set --secret bosc-deploy:tipsAppId         <github-app-id>
//   pulumi config set --secret bosc-deploy:tipsAppPrivateKey <pkcs8-pem>
//   pulumi config set --secret bosc-deploy:earlyAccessSecret <random-32-bytes-hex>
const anthropicApiKey = config.getSecret("anthropicApiKey");
const honeycombApiKey = config.getSecret("honeycombApiKey");
const tipsAppId = config.getSecret("tipsAppId");
const tipsAppPrivateKey = config.getSecret("tipsAppPrivateKey");
const earlyAccessSecret = config.getSecret("earlyAccessSecret");
const notifyGithubUsers = config.get("notifyGithubUsers") ?? "";

// The Lakebase (Databricks managed Postgres) connection string backing user-authored
// Stories (#1090). Databricks issues a short-lived OAuth token as the Postgres password,
// so the whole URL is a secret — set it out of band, never commit it:
//   pulumi config set --secret bosc-deploy:storiesLakebaseUrl \
//     postgres://<user>:<oauth-token>@<host>:5432/<database>
// It becomes the STORIES_HYPERDRIVE origin below (parsed into host/port/user/…), gated on
// features.stories. Note: because Hyperdrive caches the origin credentials, a rotated OAuth
// token needs a fresh `pulumi up` to re-push it — prefer a Databricks service principal with
// a longer-lived credential, or schedule a periodic re-apply (see issue #1138).
const storiesLakebaseUrl = config.getSecret("storiesLakebaseUrl");

// Cloudflare account that owns the resources (required — set out of band):
//   pulumi config set bosc-deploy:cloudflareAccountId <account-id>
const accountId = config.require("cloudflareAccountId");

// The Cloudflare Pages project managed by wrangler. Must match `name` in web/wrangler.toml.
// On first `pulumi up`, import the existing project before applying:
//   pulumi import cloudflare:index/pagesProject:PagesProject site-project <accountId>/<name>
const pagesProject = config.get("pagesProject") ?? "the-watermark-directory";

// The custom subdomain for the live site, e.g. "bosc.example.org" — LATE-BOUND.
// Until it's set, the stack manages KV + R2 + Turnstile and the site stays on
// <project>.pages.dev. Decided shape (#240): a **subdomain CNAME** in Route53, because
// a bare apex can't point cross-provider at pages.dev (CNAME illegal at apex; a Route53
// ALIAS only targets AWS resources). Set it when the name is chosen:
//   pulumi config set bosc-deploy:siteDomain bosc.example.org
const siteDomain = config.get("siteDomain");

// The Route53 hosted-zone id that owns `siteDomain` (required to manage the CNAME here;
// omit to attach the Pages domain but create the DNS record by hand):
//   pulumi config set bosc-deploy:route53ZoneId Z0123456789ABCDEFGHIJ
const route53ZoneId = config.get("route53ZoneId");

// Domains the Turnstile widget may be served on. The custom domain is folded in
// automatically; the-watermark-directory.pages.dev is kept so preview deploys still validate.
const previewDomains = config.getObject<string[]>("siteDomains") ?? ["the-watermark-directory.pages.dev"];
const turnstileDomains = Array.from(new Set([...(siteDomain ? [siteDomain] : []), ...previewDomains]));

// --- Submissions: KV + Turnstile (#74/#240) ---------------------------------

// Per-IP rate-limit store for the submissions Function. Bind its id as RATE_LIMIT in
// web/wrangler.toml to turn rate limiting on; until then it sits idle (fail-open).
const rateLimitKv = new cloudflare.WorkersKvNamespace("submissions-ratelimit", {
    accountId,
    title: "watermark-submissions-ratelimit",
});

// Turnstile widget guarding the public form. `secret` is flagged sensitive by the
// provider, so it stays a Pulumi secret output.
const turnstile = new cloudflare.TurnstileWidget("submissions-turnstile", {
    accountId,
    name: "watermark-submissions",
    domains: turnstileDomains,
    mode: "managed",
});

// --- Submissions: file attachments (#243) ------------------------------------
// R2 bucket for pre-uploaded submission attachments (/api/attach → /api/submit).
// SUBMISSION_ATTACHMENTS is separate from DOCS to keep evidence-chain isolation intact.
// Wire the prod bucket id as SUBMISSION_ATTACHMENTS (and the dev bucket as the preview)
// in web/wrangler.toml; until bound, /api/attach returns 503 and /api/submit silently
// drops any attachment_keys.
const submissionAttachmentsBucket = new cloudflare.R2Bucket("submission-attachments", {
    accountId,
    name: "watermark-submission-attachments",
});

const submissionAttachmentsBucketDev = new cloudflare.R2Bucket("submission-attachments-dev", {
    accountId,
    name: "watermark-submission-attachments-dev",
});

// --- Submissions: private contact store (#242) --------------------------------
// KV namespace for the submitter contact field — stored out-of-band from the public issue,
// keyed `contact:<issue-number>`, with a TTL (default 180 days). Optional: if not bound
// in wrangler.toml the contact field is accepted but not retained (never leaked). Wire
// the id as SUBMISSION_CONTACT in web/wrangler.toml once ready.
const submissionContactKv = new cloudflare.WorkersKvNamespace("submission-contact", {
    accountId,
    title: "watermark-submission-contact",
});

// --- The custom-domain exchange (only when siteDomain is set) ---------------

// Cloudflare side: register the hostname with the Pages project. This tells Cloudflare
// to expect the domain and to issue a cert once the DNS validates.
const pagesDomain = siteDomain
    ? new cloudflare.PagesDomain("site-domain", {
          accountId,
          projectName: pagesProject,
          name: siteDomain,
      })
    : undefined;

// AWS side: the Route53 CNAME that points the subdomain at the Pages project. Created
// only when the zone id is also supplied; `dependsOn` so Cloudflare is expecting the
// domain before DNS resolves to it.
const route53Record =
    siteDomain && route53ZoneId
        ? new aws.route53.Record(
              "site-cname",
              {
                  zoneId: route53ZoneId,
                  name: siteDomain,
                  type: "CNAME",
                  ttl: 300,
                  records: [`${pagesProject}.pages.dev`],
              },
              { dependsOn: pagesDomain ? [pagesDomain] : [] },
          )
        : undefined;

// --- Auth: Cognito User Pool (Epic #919, issue #924) --------------------------
// Gated on `authEnabled` (defaults false) — Cognito resources are stateful and
// destructive to remove (existing users and sessions are lost). Provision the User Pool
// once and leave `authEnabled` true. Flip to false only when decommissioning.
//   pulumi config set bosc-deploy:authEnabled true
//
// The KV namespaces (JWKS_CACHE, AUTH_PREFS) are always created — they're cheap and
// the bind-in-wrangler.toml step is the actual activation gate, not Pulumi.
const authEnabled = config.getBoolean("authEnabled") ?? false;

// Hosted UI domain prefix. The full domain becomes:
//   <prefix>.auth.<region>.amazoncognito.com
// Set a custom domain in the console after pool creation if desired (requires an ACM
// cert in us-east-1). A custom domain cannot be set here without the cert ARN.
//   pulumi config set bosc-deploy:cognitoDomainPrefix watermark-auth
const cognitoDomainPrefix = config.get("cognitoDomainPrefix") ?? "watermark-auth";

// The AWS region for Cognito. A dedicated provider is constructed from this value and
// passed explicitly to every Cognito resource, so the deployed region always matches
// the issuer/domain strings exported below. Using the ambient provider would silently
// produce a mismatch if AWS_DEFAULT_REGION differs from the intended Cognito region.
//   pulumi config set bosc-deploy:cognitoRegion us-east-1
const cognitoRegion = config.get("cognitoRegion") ?? "us-east-1";
const cognitoProvider = new aws.Provider("cognito-provider", {
    region: cognitoRegion as aws.Region,
});

// Callback + logout URLs for the app client. The site domain is folded in automatically
// when set; localhost:4321 is always included for local dev.
const appBaseUrl = siteDomain ? `https://${siteDomain}` : null;
const cognitoCallbackUrls = [
    ...(appBaseUrl ? [`${appBaseUrl}/account/callback`] : []),
    "http://localhost:4321/account/callback",
];
const cognitoLogoutUrls = [
    ...(appBaseUrl ? [`${appBaseUrl}/`] : []),
    "http://localhost:4321/",
];

const userPool = authEnabled
    ? new aws.cognito.UserPool("auth-pool", {
          name: "watermark-prod",
          autoVerifiedAttributes: ["email"],
          usernameAttributes: ["email"],
          schemas: [
              {
                  name: "email",
                  attributeDataType: "String",
                  required: true,
                  mutable: true,
              },
              // Per-site admin scope: a comma-separated list of site slugs the user
              // may curate. Read by the `site-admin` role path in _lib/auth.ts.
              {
                  name: "admin_sites",
                  attributeDataType: "String",
                  required: false,
                  mutable: true,
                  stringAttributeConstraints: {
                      minLength: "0",
                      maxLength: "2048",
                  },
              },
          ],
          passwordPolicy: {
              minimumLength: 8,
              requireLowercase: true,
              requireUppercase: true,
              requireNumbers: true,
              requireSymbols: false,
          },
          accountRecoverySetting: {
              recoveryMechanisms: [{ name: "verified_email", priority: 1 }],
          },
          // Prevent user-existence oracle (mitigates enumeration via sign-in errors).
          userAttributeUpdateSettings: {
              attributesRequireVerificationBeforeUpdates: ["email"],
          },
      }, { provider: cognitoProvider })
    : undefined;

// Hosted UI domain (Cognito-hosted subdomain; upgrading to a custom domain requires a
// separate ACM cert and a console step not modelled here).
const userPoolDomain = authEnabled && userPool
    ? new aws.cognito.UserPoolDomain("auth-domain", {
          domain: cognitoDomainPrefix,
          userPoolId: userPool.id,
      }, { provider: cognitoProvider })
    : undefined;

// App client: public client (no secret), PKCE Authorization Code grant only.
// Social providers can be added later in the console; `supportedIdentityProviders`
// starts with COGNITO only to keep the scope minimal.
const userPoolClient = authEnabled && userPool
    ? new aws.cognito.UserPoolClient("auth-client", {
          name: "watermark-web",
          userPoolId: userPool.id,
          generateSecret: false,
          supportedIdentityProviders: ["COGNITO"],
          allowedOauthFlows: ["code"],
          allowedOauthScopes: ["openid", "email", "profile"],
          allowedOauthFlowsUserPoolClient: true,
          callbackUrls: cognitoCallbackUrls,
          logoutUrls: cognitoLogoutUrls,
          // Refresh-token auth is needed for the /api/account/refresh endpoint.
          explicitAuthFlows: ["ALLOW_REFRESH_TOKEN_AUTH"],
          preventUserExistenceErrors: "ENABLED",
      }, { provider: cognitoProvider })
    : undefined;

// User Pool Groups — three privilege tiers (see docs/auth.md).
// `extractRole()` in _lib/auth.ts picks the highest group in the ID token's
// `cognito:groups` claim: admin > site-admin > standard (unauthenticated users
// have no group and are rejected by auth-gated endpoints).
const groupStandard = authEnabled && userPool
    ? new aws.cognito.UserGroup("auth-group-standard", {
          name: "standard",
          userPoolId: userPool.id,
      }, { provider: cognitoProvider })
    : undefined;

const groupSiteAdmin = authEnabled && userPool
    ? new aws.cognito.UserGroup("auth-group-site-admin", {
          name: "site-admin",
          userPoolId: userPool.id,
      }, { provider: cognitoProvider })
    : undefined;

const groupAdmin = authEnabled && userPool
    ? new aws.cognito.UserGroup("auth-group-admin", {
          name: "admin",
          userPoolId: userPool.id,
      }, { provider: cognitoProvider })
    : undefined;

// early-access group: invited users who bypass the pre-launch gate (#1010).
// Precedence 20 — below site-admin (10), above standard (30).
const groupEarlyAccess = authEnabled && userPool
    ? new aws.cognito.UserGroup("auth-group-early-access", {
          name: "early-access",
          description: "Early access — bypasses pre-launch gate",
          userPoolId: userPool.id,
          precedence: 20,
      }, { provider: cognitoProvider })
    : undefined;

// Suppress unused-variable warnings for the group resources — they're managed for
// side-effect (the groups exist in Cognito) and their ids aren't needed downstream.
void groupStandard;
void groupSiteAdmin;
void groupAdmin;
void groupEarlyAccess;

// --- Auth: KV namespaces (always created — cheap; activation gate is wrangler.toml) ---

// JWKS key cache: caches Cognito's public-key document (1-hour TTL) so JWT verification
// doesn't cold-fetch on every request. Wire the id as JWKS_CACHE in wrangler.toml.
const jwksCacheKv = new cloudflare.WorkersKvNamespace("auth-jwks-cache", {
    accountId,
    title: "watermark-auth-jwks-cache",
});

// User profile + notification prefs, keyed by Cognito sub (Epic #921).
// Wire the id as AUTH_PREFS in wrangler.toml.
const authPrefsKv = new cloudflare.WorkersKvNamespace("auth-prefs", {
    accountId,
    title: "watermark-auth-prefs",
});

// ---------------------------------------------------------------------------
// User-authored Stories: Hyperdrive → Lakebase (Epic #1090 / issue #1138)
// ---------------------------------------------------------------------------
// The Workers runtime can't open a raw Postgres socket to Databricks Lakebase, so the
// /api/stories Functions reach it through a Cloudflare Hyperdrive binding (pooling +
// `cloudflare:sockets`, via postgres.js — see web/functions/api/_lib/pg.ts). This declares
// the Hyperdrive config over the Lakebase connection string and exports its id so the
// wrangler `[[hyperdrive]]` `id` can be filled from `pulumi stack output storiesHyperdriveId`.
//
// Gated on features.stories (like the ask/auth guards): only provisioned when the seam goes
// live, so the short-lived Lakebase OAuth token isn't required until then. The `stories=true
// but no storiesLakebaseUrl` config guard lives with the other guards below.

// Parse the `postgres://user:password@host:port/database` secret into the structured origin
// Hyperdrive wants. Runs inside `.apply()` so it stays a secret (password included); throwing
// here fails `pulumi up` with a clear message.
function parseLakebaseOrigin(url: string): cloudflare.types.input.HyperdriveConfigOrigin {
    let parsed: URL;
    try {
        parsed = new URL(url);
    } catch {
        throw new Error(
            "bosc-deploy:storiesLakebaseUrl is not a valid URL — expected " +
            "postgres://user:password@host:port/database",
        );
    }
    const scheme = parsed.protocol.replace(/:$/, "");
    if (scheme !== "postgres" && scheme !== "postgresql") {
        throw new Error(
            `bosc-deploy:storiesLakebaseUrl scheme must be postgres:// or postgresql:// (got "${scheme}://")`,
        );
    }
    const database = decodeURIComponent(parsed.pathname.replace(/^\//, ""));
    if (!parsed.hostname || !parsed.username || !database) {
        throw new Error(
            "bosc-deploy:storiesLakebaseUrl must include host, user, and database " +
            "(postgres://user:password@host:port/database)",
        );
    }
    return {
        scheme,
        host: parsed.hostname,
        port: parsed.port ? Number(parsed.port) : 5432,
        database,
        user: decodeURIComponent(parsed.username),
        password: decodeURIComponent(parsed.password),
    };
}

const storiesHyperdrive =
    features.stories && storiesLakebaseUrl
        ? new cloudflare.HyperdriveConfig("stories-hyperdrive", {
              accountId,
              name: "watermark-stories",
              origin: storiesLakebaseUrl.apply(parseLakebaseOrigin),
          })
        : undefined;

// ---------------------------------------------------------------------------
// Notification Lambda (Epic E #938/#939)
// ---------------------------------------------------------------------------
// GitHub webhook → Lambda → AUTH_PREFS lookup → SES email dispatch.
// Gated on `notifyEnabled` (defaults false) — SES identity + Lambda are created
// only when explicitly enabled. Flip once SES domain verification is complete.
//   pulumi config set bosc-deploy:notifyEnabled true
//   pulumi config set --secret bosc-deploy:githubWebhookSecret <secret>
//   pulumi config set --secret bosc-deploy:unsubSecret <secret>
//   pulumi config set bosc-deploy:sesFromAddress notifications@watermarkdirectory.org
//
// The Lambda zip must be built before `pulumi up`:
//   cd lambda/notify && npm install && npm run build
// Then Pulumi reads ../lambda/notify/dist/ as a FileArchive.

const notifyEnabled = config.getBoolean("notifyEnabled") ?? false;

// SES from-address (e.g. "notifications@watermarkdirectory.org").
const sesFromAddress = config.get("sesFromAddress") ?? "";

// Secrets (set out of band via `pulumi config set --secret`).
const githubWebhookSecret = config.getSecret("githubWebhookSecret");
const unsubSecret = config.getSecret("unsubSecret");
// Cloudflare API token for KV access from Lambda (separate from the CF provider env var).
//   pulumi config set --secret bosc-deploy:cloudflareApiToken <token>
const notifyCloudflareApiToken = config.getSecret("cloudflareApiToken");

// SES email identity (domain or address). Created in the same region as Cognito.
// Operator must complete DNS verification in Route53 after the first `pulumi up`.
const sesIdentity =
  notifyEnabled && sesFromAddress
    ? new aws.ses.EmailIdentity(
        "notify-ses-identity",
        { email: sesFromAddress },
        { provider: cognitoProvider },
      )
    : undefined;

// IAM role for the notify Lambda.
const notifyRole =
  notifyEnabled
    ? new aws.iam.Role("notify-lambda-role", {
          name: "watermark-notify-lambda",
          assumeRolePolicy: JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Effect: "Allow",
                Principal: { Service: "lambda.amazonaws.com" },
                Action: "sts:AssumeRole",
              },
            ],
          }),
      })
    : undefined;

// Attach basic execution (CloudWatch logs) + SES send permission.
const notifyRolePolicy =
  notifyEnabled && notifyRole
    ? new aws.iam.RolePolicy("notify-lambda-policy", {
          role: notifyRole.id,
          policy: JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Effect: "Allow",
                Action: ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                Resource: "arn:aws:logs:*:*:*",
              },
              {
                Effect: "Allow",
                Action: ["ses:SendEmail", "ses:SendRawEmail"],
                Resource: "*",
              },
            ],
          }),
      })
    : undefined;

void notifyRolePolicy;

// Lambda function. Code is read from the pre-built dist/ directory.
// Build: cd lambda/notify && npm ci && npm run build
const notifyLambda =
  notifyEnabled && notifyRole
    ? new aws.lambda.Function(
          "notify-lambda",
          {
            name: "watermark-notify",
            runtime: "nodejs22.x" as aws.lambda.Runtime,
            handler: "index.handler",
            role: notifyRole.arn,
            code: new pulumi.asset.FileArchive("../lambda/notify/dist"),
            timeout: 60,
            environment: {
              variables: {
                SES_FROM_ADDRESS: sesFromAddress,
                CLOUDFLARE_ACCOUNT_ID: accountId,
                AUTH_PREFS_NAMESPACE_ID: authPrefsKv.id,
                SITE_URL: siteDomain
                  ? `https://${siteDomain}`
                  : `https://${pagesProject}.pages.dev`,
                ...(githubWebhookSecret ? { GITHUB_WEBHOOK_SECRET: githubWebhookSecret } : {}),
                ...(unsubSecret ? { UNSUB_SECRET: unsubSecret } : {}),
                ...(notifyCloudflareApiToken
                  ? { CLOUDFLARE_API_TOKEN: notifyCloudflareApiToken }
                  : {}),
              },
            },
          },
          { provider: cognitoProvider, dependsOn: notifyRole ? [notifyRole] : [] },
      )
    : undefined;

// Lambda Function URL — exposes the Lambda as an HTTPS endpoint for GitHub webhooks.
// No IAM auth (the webhook signature verification is the credential).
const notifyFunctionUrl =
  notifyEnabled && notifyLambda
    ? new aws.lambda.FunctionUrl("notify-lambda-url", {
          functionName: notifyLambda.name,
          authorizationType: "NONE",
      }, { provider: cognitoProvider })
    : undefined;

// EventBridge rule: fires once per day to trigger the digest flush path.
const notifyDigestRule =
  notifyEnabled && notifyLambda
    ? new aws.cloudwatch.EventRule("notify-digest-rule", {
          name: "watermark-notify-daily-digest",
          description: "Daily notification digest flush for AUTH_PREFS subscribers",
          scheduleExpression: "cron(0 8 * * ? *)", // 08:00 UTC daily
      }, { provider: cognitoProvider })
    : undefined;

const notifyDigestTarget =
  notifyEnabled && notifyLambda && notifyDigestRule
    ? new aws.cloudwatch.EventTarget("notify-digest-target", {
          rule: notifyDigestRule.name,
          arn: notifyLambda.arn,
      }, { provider: cognitoProvider })
    : undefined;

void notifyDigestTarget;

// Allow EventBridge to invoke the Lambda.
const notifyDigestPermission =
  notifyEnabled && notifyLambda && notifyDigestRule
    ? new aws.lambda.Permission("notify-digest-permission", {
          action: "lambda:InvokeFunction",
          function: notifyLambda.name,
          principal: "events.amazonaws.com",
          sourceArn: notifyDigestRule.arn,
      }, { provider: cognitoProvider })
    : undefined;

void notifyDigestPermission;

// ---------------------------------------------------------------------------
// Pages project env vars + feature toggles
// ---------------------------------------------------------------------------
// Pulumi writes all env vars it can know to the Pages project directly, so the
// operator never has to copy values from `pulumi stack output` into the dashboard.
//
// Layout:
//   • Feature toggles from features.yaml  — plain_text; flip + pulumi up to activate
//   • Cognito IDs (when authEnabled)       — plain_text; Pulumi just provisioned them
//   • TURNSTILE_SECRET_KEY                — secret_text; Pulumi provisioned it
//   • External secrets from Pulumi config — secret_text; operator sets once, Pulumi writes
//
// KV bindings and R2 bindings are NOT set here — those remain in wrangler.toml
// because wrangler applies them per-deployment (a future improvement could move them here).

// Configuration guards — catch mismatches before writing env vars to Pages.
if (features.ask && !anthropicApiKey) {
    throw new Error(
        "features.yaml: ask=true but bosc-deploy:anthropicApiKey is not set in Pulumi config. " +
        "Run: pulumi config set --secret bosc-deploy:anthropicApiKey <key>",
    );
}
if (features.auth && !authEnabled) {
    throw new Error(
        "features.yaml: auth=true but bosc-deploy:authEnabled is not set to true in Pulumi config. " +
        "Run: pulumi config set bosc-deploy:authEnabled true",
    );
}
if (features.stories && !storiesLakebaseUrl) {
    throw new Error(
        "features.yaml: stories=true but bosc-deploy:storiesLakebaseUrl is not set in Pulumi config. " +
        "Run: pulumi config set --secret bosc-deploy:storiesLakebaseUrl postgres://user:password@host:5432/database",
    );
}

type PageEnvVar = { value: pulumi.Input<string>; type: pulumi.Input<string> };
const pageEnvVars: Record<string, PageEnvVar> = {
    // Feature toggles (features.yaml)
    PRE_LAUNCH_ENABLED:  { value: features.preLaunch   ? "true" : "false", type: "plain_text" },
    SUBMISSIONS_ENABLED: { value: features.submissions ? "true" : "false", type: "plain_text" },
    ASK_ENABLED:         { value: features.ask         ? "true" : "false", type: "plain_text" },
    DOCS_ENABLED:        { value: features.docs        ? "true" : "false", type: "plain_text" },
    MCP_ENABLED:         { value: features.mcp         ? "true" : "false", type: "plain_text" },
    // rum gates the edge beacon AND the Astro build-time script injection
    RUM_ENABLED:         { value: features.rum         ? "true" : "false", type: "plain_text" },
    PUBLIC_RUM_ENABLED:  { value: features.rum         ? "true" : "false", type: "plain_text" },
    AUTH_ENABLED:        { value: features.auth        ? "true" : "false", type: "plain_text" },
    // stories gates the /api/stories Functions kill switch AND the Astro build-time UI gate
    STORIES_ENABLED:        { value: features.stories  ? "true" : "false", type: "plain_text" },
    PUBLIC_STORIES_ENABLED: { value: features.stories  ? "true" : "false", type: "plain_text" },
    // Computed non-secret vars
    APP_BASE_URL: {
        value: siteDomain ? `https://${siteDomain}` : `https://${pagesProject}.pages.dev`,
        type: "plain_text",
    },
    // Turnstile secret (Pulumi provisioned it; written as secret_text so it's encrypted in CF)
    TURNSTILE_SECRET_KEY: { value: turnstile.secret, type: "secret_text" },
};

// Cognito identifiers — added only when the pool was actually provisioned
if (authEnabled && userPool && userPoolClient && userPoolDomain) {
    const cognitoDomainFull = `${cognitoDomainPrefix}.auth.${cognitoRegion}.amazoncognito.com`;
    pageEnvVars.COGNITO_REGION           = { value: cognitoRegion,        type: "plain_text" };
    pageEnvVars.COGNITO_USER_POOL_ID     = { value: userPool.id,          type: "plain_text" };
    pageEnvVars.COGNITO_CLIENT_ID        = { value: userPoolClient.id,    type: "plain_text" };
    pageEnvVars.COGNITO_DOMAIN           = { value: cognitoDomainFull,    type: "plain_text" };
    // PUBLIC_* variants are consumed by the Astro build (build-time env injection)
    pageEnvVars.PUBLIC_COGNITO_CLIENT_ID = { value: userPoolClient.id,    type: "plain_text" };
    pageEnvVars.PUBLIC_COGNITO_DOMAIN    = { value: cognitoDomainFull,    type: "plain_text" };
}

// External secrets — only set when the operator has provisioned the Pulumi config secret
if (anthropicApiKey)   pageEnvVars.ANTHROPIC_API_KEY    = { value: anthropicApiKey,    type: "secret_text" };
if (honeycombApiKey)   pageEnvVars.HONEYCOMB_API_KEY    = { value: honeycombApiKey,    type: "secret_text" };
if (tipsAppId)         pageEnvVars.TIPS_APP_ID          = { value: tipsAppId,          type: "secret_text" };
if (tipsAppPrivateKey) pageEnvVars.TIPS_APP_PRIVATE_KEY = { value: tipsAppPrivateKey,  type: "secret_text" };
if (earlyAccessSecret) pageEnvVars.EARLY_ACCESS_SECRET  = { value: earlyAccessSecret,  type: "secret_text" };
// Optional plain-text overrides — only added when set so omitting them doesn't wipe a value
// that hasn't been migrated yet. (Other optional vars like MCP_BUDGET_* and RUM_HONEYCOMB_DATASET
// have code-level defaults and are not currently deployed; add via Pulumi config if needed.)
if (notifyGithubUsers) pageEnvVars.NOTIFY_GITHUB_USERS = { value: notifyGithubUsers,  type: "plain_text" };

// The Pages project resource. Pulumi owns project-level config; wrangler owns deployments.
// Import on first apply if the project already exists (see comment at top of file).
new cloudflare.PagesProject("site-project", {
    accountId,
    name: pagesProject,
    productionBranch: "main",
    deploymentConfigs: {
        production: {
            envVars: pageEnvVars,
        },
    },
});

// ---------------------------------------------------------------------------
// Outputs — wire these into the rest of the seam (see README + docs/)
// ---------------------------------------------------------------------------

// --- Submissions (#240 / #74) ---
/** KV namespace id → `web/wrangler.toml` `[[kv_namespaces]]` `id` (RATE_LIMIT). */
export const rateLimitKvNamespaceId = rateLimitKv.id;
/** Public Turnstile site key → the `PUBLIC_TURNSTILE_SITE_KEY` build var. */
export const turnstileSiteKey = turnstile.sitekey;
/** Secret Turnstile key → the `TURNSTILE_SECRET_KEY` Function secret (a secret output). */
export const turnstileSecretKey = turnstile.secret;
/** The live site URL once the custom domain validates (else the pages.dev default). */
export const siteUrl = siteDomain ? `https://${siteDomain}` : `https://${pagesProject}.pages.dev`;
/** Cloudflare's validation status for the custom domain ("active" once the cert issues). */
export const siteDomainStatus = pagesDomain ? pagesDomain.status : pulumi.output("not-configured");
/** The Route53 record FQDN, when Pulumi manages the DNS side. */
export const route53RecordFqdn = route53Record ? route53Record.fqdn : pulumi.output("not-managed");

// --- Submissions: attachments (#243) ---
/** R2 bucket name → `web/wrangler.toml` `bucket_name` (SUBMISSION_ATTACHMENTS). */
export const submissionAttachmentsBucketName = submissionAttachmentsBucket.name;
/** R2 dev bucket name → `web/wrangler.toml` `preview_bucket_name` (SUBMISSION_ATTACHMENTS). */
export const submissionAttachmentsBucketDevName = submissionAttachmentsBucketDev.name;

// --- Submissions: contact store (#242) ---
/** KV namespace id → `web/wrangler.toml` `[[kv_namespaces]]` `id` (SUBMISSION_CONTACT). */
export const submissionContactKvNamespaceId = submissionContactKv.id;

// --- Auth: Cognito (#924) ---
/** Cognito User Pool id → `COGNITO_USER_POOL_ID` in wrangler.toml `[vars]`. */
export const cognitoUserPoolId = userPool ? userPool.id : pulumi.output("not-configured");
/** App client id → `COGNITO_CLIENT_ID` in wrangler.toml `[vars]` and the CI build env. */
export const cognitoClientId = userPoolClient ? userPoolClient.id : pulumi.output("not-configured");
/** Hosted UI domain → `COGNITO_DOMAIN` in wrangler.toml `[vars]` and the CI build env. */
export const cognitoDomain = userPoolDomain
    ? pulumi.output(`${cognitoDomainPrefix}.auth.${cognitoRegion}.amazoncognito.com`)
    : pulumi.output("not-configured");
/** AWS region → `COGNITO_REGION` in wrangler.toml `[vars]`. */
export const cognitoRegionOut = pulumi.output(cognitoRegion);

// --- Auth: KV namespaces (#919) ---
/** KV namespace id → `web/wrangler.toml` `[[kv_namespaces]]` `id` (JWKS_CACHE). */
export const jwksCacheKvNamespaceId = jwksCacheKv.id;
/** KV namespace id → `web/wrangler.toml` `[[kv_namespaces]]` `id` (AUTH_PREFS). */
export const authPrefsKvNamespaceId = authPrefsKv.id;

// --- User-authored Stories: Hyperdrive → Lakebase (#1090 / #1138) ---
/** Hyperdrive config id → `web/wrangler.toml` `[[hyperdrive]]` `id` (STORIES_HYPERDRIVE). */
export const storiesHyperdriveId = storiesHyperdrive
    ? storiesHyperdrive.id
    : pulumi.output("not-configured");

// --- Notification Lambda (#938/#939) ---
/** GitHub webhook URL — register in the repo's webhook settings when notifyEnabled is true. */
export const notifyWebhookUrl = notifyFunctionUrl
    ? notifyFunctionUrl.functionUrl
    : pulumi.output("not-configured");
/** SES identity ARN — DNS verification records must be set before first send. */
export const sesIdentityArn = sesIdentity ? sesIdentity.arn : pulumi.output("not-configured");
