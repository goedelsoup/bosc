# Secret rotation runbook (`deploy/`)

Rotation is the moment these secrets are most likely to take the live site down — a
mis-ordered roll lands us in the same user-facing `500 {"error":"endpoint is misconfigured"}`
that [#1539](https://github.com/watermark-directory/the-watermark-directory/issues/1539) was
opened over. This file is the procedure: what issues each secret, how to roll it at the
provider, the exact Pulumi sequence, and the overlap ordering that keeps the forms up.

Provisioning a secret for the *first* time is the easy case and lives in
[`Pulumi.prod.yaml`](Pulumi.prod.yaml). This file is about replacing one that is already live.

> **The config namespace is `watermark-deploy:`** — the Pulumi **project** name
> ([`Pulumi.yaml`](Pulumi.yaml)), not the `bosc-deploy` S3 state prefix. `pulumi config set`
> accepts any namespace silently, so `pulumi config set --secret bosc-deploy:anthropicApiKey`
> "succeeds", writes a key nothing reads, and the rotation lands nowhere. The commands below
> are the correct ones.

## The three classes

Which class a secret belongs to determines the whole procedure, so start here.

| Class | Who issues the value | Rotation shape |
| --- | --- | --- |
| **Pulumi-provisioned** | a Cloudflare resource Pulumi owns; the value is a resource *output* | roll it at the provider **out of band**, then `pulumi refresh` so state catches the new value, then `pulumi up` to push it |
| **Operator-supplied** | an external provider (Anthropic, Honeycomb, GitHub, Databricks) or `openssl rand` | make the new value valid upstream **first**, then `pulumi config set --secret` + `pulumi up`, then revoke the old |
| **Wrangler-set** | operator, but written straight to Pages — Pulumi never sees it | `wrangler pages secret put`; no `pulumi up` involved |

## Inventory

Every secret that reaches production, its class, and what breaks if the rotation is botched.

| Secret (env var) | Config key | Class | Consumers | Blast radius |
| --- | --- | --- | --- | --- |
| `TURNSTILE_SECRET_KEY` | *(none — `turnstile.secret`)* | Pulumi-provisioned | [`ask.ts`](../web/functions/api/ask.ts), [`submit.ts`](../web/functions/api/submit.ts) | **both** public forms at once |
| `ANTHROPIC_API_KEY` | `anthropicApiKey` | operator-supplied | [`ask.ts`](../web/functions/api/ask.ts) | `/api/ask` |
| `HONEYCOMB_API_KEY` | `honeycombApiKey` | operator-supplied | edge OTel, [`rum.ts`](../web/functions/api/rum.ts) | telemetry only — **never user-facing** |
| `TIPS_APP_ID` | `tipsAppId` | operator-supplied | [`submit.ts`](../web/functions/api/submit.ts) | `/api/submit` |
| `TIPS_APP_PRIVATE_KEY` | `tipsAppPrivateKey` | operator-supplied | [`submit.ts`](../web/functions/api/submit.ts) | `/api/submit` |
| `EARLY_ACCESS_SECRET` | `earlyAccessSecret` | operator-supplied | [`_middleware.ts`](../web/functions/_middleware.ts) | invalidates every outstanding `__ea` cookie (that is often the *point*) |
| *(Hyperdrive origin)* | `storiesLakebaseUrl` | operator-supplied | `STORIES_HYPERDRIVE` origin **and** the notify Lambda's `LAKEBASE_URL` | stories/contacts + the digest mailer |
| *(Lambda env)* | `githubWebhookSecret` | operator-supplied | [`lambda/notify`](../lambda/notify) | webhook rejected → no notifications |
| *(Lambda env)* | `unsubSecret` | operator-supplied | [`lambda/notify`](../lambda/notify) | breaks every previously-mailed unsubscribe link |
| `ASK_PLUGIN_TOKEN` | *(none)* | wrangler-set | [`askPluginAuth.ts`](../web/functions/api/_lib/askPluginAuth.ts) | the ChatGPT-plugin Turnstile bypass |
| `COGNITO_CLIENT_SECRET` | *(none)* | wrangler-set | the auth layer ([`docs/auth.md`](../docs/auth.md)) | login |

Two credentials sit *outside* this stack and rotate on their own terms:

- **`CLOUDFLARE_API_TOKEN`** — the provider token, held as a GitHub Actions secret and used by
  both [`deploy-infra.yml`](../.github/workflows/deploy-infra.yml) and
  [`pages.yml`](../.github/workflows/pages.yml). Rotating it is a GitHub-secret edit, not a
  `pulumi up`; needs **Workers KV: Edit** + **Turnstile: Edit** + **Pages: Edit** + **R2: Edit**
  (and **Turnstile Sites: Write**, for the rotate below).
- **AWS** — assumed via OIDC (`DEPLOY_AWS_ROLE_ARN`). There is no static key to rotate. Keep it
  that way.

## How a rotated value reaches the live Functions

Three hops. A rotation that "didn't work" has almost always stalled at one of them, and they
fail in different, non-obvious ways:

1. **`pulumi config set --secret`** writes the encrypted value into
   [`Pulumi.prod.yaml`](Pulumi.prod.yaml) (awskms-encrypted; safe to commit).
2. **`pulumi up`** writes it to the Pages **project** as a `secret_text` env var
   ([`index.ts`](index.ts) `pageEnvVars`). At this point it exists on the project.
3. The **deployment** serves it. Cloudflare's docs are inconsistent about whether a project-level
   env-var change is picked up by already-live deployments or only by the next one, so **do not
   assume**: verify (below), and if the old value is still being served, run
   [`pages.yml`](../.github/workflows/pages.yml) with `deploy: true` to cut a fresh deployment.

**A Pages redeploy is safe for secrets and hostile to plaintext vars.** `wrangler pages deploy`
makes [`web/wrangler.toml`](../web/wrangler.toml) authoritative for `[vars]` and strips any
plaintext var not listed there — but Pages **secrets persist across deploys**. So the redeploy in
step 3 will not undo the rotation. It *will* strip any plaintext var that lives only in Pulumi,
which is exactly how `/api/submit` broke before; that is a `[vars]` sync problem, not a rotation
problem, but a rotation is a common time to trip over it.

## The universal ordering

For any operator-supplied secret, keep an **overlap window** — a period where both the old and
new values are accepted upstream — and only close it once production is verified on the new one:

```text
1. issue the new value at the provider          ← old still valid: overlap window OPEN
2. pulumi config set --secret …                 ← nothing live has changed yet
3. pulumi up                                    ← project now carries the new value
4. verify production                            ← ./rotate.sh verify
5. revoke the old value at the provider         ← overlap window CLOSED
```

Steps 1 and 5 are the ones that are easy to get backwards. Revoking first (or issuing a
replacement that invalidates its predecessor) means production runs on a dead credential for the
length of steps 2–4 — minutes at best, and longer if `pulumi up` needs a fix.

**Compromise is the deliberate exception.** If a value has leaked, revoke it *first* and accept
the outage: a few minutes of `500 misconfigured` beats a live credential in someone else's hands.
Say so in the incident note so the inverted ordering doesn't read as a mistake later.

## Per-secret procedures

Every command below runs from **`deploy/`** (that is where the Pulumi project and `rotate.sh`
live). The numbered comments map onto the five steps above.

### `TURNSTILE_SECRET_KEY` — Pulumi-provisioned, shared by submit **and** ask

The only secret in the stack that Pulumi *issues* rather than carries: it is the `secret` output of
the `cloudflare.TurnstileWidget` in [`index.ts`](index.ts). The Pulumi provider exposes no rotate
operation, so rotation is a Cloudflare API call plus a state refresh.

**Rotate in place; do not replace the widget.** Replacing it mints a **new sitekey**, and the
sitekey is baked into the site at *build* time (`PUBLIC_TURNSTILE_SITE_KEY`, a GitHub repo
variable read by [`pages.yml`](../.github/workflows/pages.yml)) — so a replacement is a secret roll
*and* a repo-variable edit *and* a full site rebuild, with both forms broken in between. Rotation
in place keeps the sitekey and touches only the secret half.

From `deploy/`, with `CLOUDFLARE_API_TOKEN` exported (it needs **Turnstile Sites: Write** on top
of the provider scopes):

```bash
./rotate.sh turnstile
```

which is exactly these three steps — run them by hand if you want to stop between any two:

```bash
# 1. Rotate at Cloudflare. invalidate_immediately=false keeps the OLD secret valid for two
#    hours — that grace period IS the overlap window, so pass it explicitly rather than
#    relying on the API default.
ACCOUNT=$(pulumi config get watermark-deploy:cloudflareAccountId)
SITEKEY=$(pulumi stack output turnstileSiteKey)
curl -fsS -X POST \
  "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT}/challenges/widgets/${SITEKEY}/rotate_secret" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"invalidate_immediately": false}'

# 2. Pull the new secret into Pulumi state, then push it to Pages. The refresh is NOT
#    optional: without it Pulumi still holds the pre-rotation value and `up` writes the
#    stale secret back, so the rotation silently reverts.
pulumi up --refresh

# 3. Verify — inside the two-hour window.
./rotate.sh verify
```

Three things to hold onto:

- **The whole rotation must finish inside the two-hour grace period.** After it expires the old
  secret is dead; if the new one has not reached the deployment by then, `/api/submit` **and**
  `/api/ask` both start returning `403 verification failed`. Do not start this at the end of the day.
- **You cannot rotate again during the grace period.** A failed attempt is not retryable for two
  hours — fix forward with `pulumi up --refresh`, don't re-rotate.
- **`pulumi refresh` works here** because Cloudflare's widget `GET` returns `secret`, so the
  refreshed state carries the rotated value. CI already passes `refresh: true`
  ([`deploy-infra.yml`](../.github/workflows/deploy-infra.yml)), so an apply through the workflow
  refreshes on its own; a *local* `pulumi up` does not, hence the explicit `--refresh` above.

### `ANTHROPIC_API_KEY` — operator-supplied

Issued in the Anthropic Console. Anthropic keys are independent — creating a new one does not
invalidate the old, so the overlap window is free and there is no excuse for skipping it.

```bash
# 1. Create the new key in the Anthropic Console (console.anthropic.com → API keys).
#    Leave the old one active.
# 2-3. Set + apply. The value is prompted for without echo and handed to Pulumi on stdin,
#      so it never lands in shell history or in `ps`.
./rotate.sh set anthropicApiKey        # prompts, then runs `pulumi up`
# 4. Verify.
./rotate.sh verify --deep              # --deep makes a real /api/ask call, exercising the key
# 5. Delete the old key in the Console.
```

`verify` without `--deep` only proves the variable is *present* — a syntactically valid but wrong
key passes it. `--deep` needs `ASK_PLUGIN_TOKEN` (the Turnstile bypass) to make a scripted call;
without it, do step 4 by hand in a browser on [/ask](https://the.watermark.directory/ask) and
confirm you get an answer or a grounded refusal rather than a 500.

### `TIPS_APP_ID` / `TIPS_APP_PRIVATE_KEY` — operator-supplied

The GitHub App that files submissions as issues. **The App ID is not a secret and does not
rotate** — it is stored as a Pulumi secret only for uniformity. Only the private key rotates.

A GitHub App may hold **several private keys at once**, which is what makes the overlap window
possible: generate the new key before deleting the old.

```bash
# 1. GitHub → the App's settings → Private keys → "Generate a private key" (downloads PKCS#1).
# 2. Convert to PKCS#8 — the Workers runtime's WebCrypto imports PKCS#8 only:
openssl pkcs8 -topk8 -nocrypt -in downloaded.pem -out tips-app.pk8.pem
# 3-4. Set + apply. Multi-line values can't come from a no-echo prompt, so pipe the file in.
./rotate.sh set tipsAppPrivateKey < tips-app.pk8.pem
# 5. Verify, then delete the old key in the App settings and shred the local files.
./rotate.sh verify
shred -u downloaded.pem tips-app.pk8.pem 2>/dev/null || rm -f downloaded.pem tips-app.pk8.pem
```

### `HONEYCOMB_API_KEY` — operator-supplied, three copies

The least urgent and the easiest to half-rotate: the same key is used in **three** places, only
one of which Pulumi owns.

1. the Pages Function secret (`watermark-deploy:honeycombApiKey` → `pulumi up`);
2. the **`HONEYCOMB_API_KEY` GitHub Actions secret**, read by
   [`research.yml`](../.github/workflows/research.yml) and
   [`agent-worker.yml`](../.github/workflows/agent-worker.yml);
3. local `.env` files — `WATERMARK_HONEYCOMB_API_KEY`, the settings-prefixed name (see
   [`.env.example`](../.env.example)), on every developer's machine.

Rotate all three inside one overlap window, then revoke. Missing (2) is silent: the workflows keep
running and simply stop reporting spans. A failure here never reaches a user, so if you are
mid-incident on something else, this one can wait.

### `EARLY_ACCESS_SECRET` — operator-supplied, no overlap possible

Signs the `__ea` cookie that lets invited users past the pre-launch gate. The cookie is stateless,
so **rotating it invalidates every outstanding cookie immediately** — there is no dual-validity
mechanism and no overlap window. That is a feature: it is the only way to revoke early access
before the embedded 7-day expiry (see [`_middleware.ts`](../web/functions/_middleware.ts)).

```bash
openssl rand -hex 32 | ./rotate.sh set earlyAccessSecret
```

Everyone in the beta cohort must re-authenticate afterwards. With `preLaunch: false` in
[`features.yaml`](features.yaml) the gate is inert and the blast radius is nil — check the flag
before worrying about the cohort.

### `storiesLakebaseUrl` — the token that expires on its own

Not a rotation so much as a standing liability, and the reason
[#1138](https://github.com/watermark-directory/the-watermark-directory/issues/1138) is open.
Databricks issues a **short-lived OAuth token** as the Postgres password, so the whole connection
string is a secret — and it goes stale whether or not anyone rotates it.

Two consumers, one secret:

- **`STORIES_HYPERDRIVE`** — Hyperdrive **caches the origin credentials**, so a refreshed token
  does not reach it until a `pulumi up` re-pushes the origin. Nothing about the Workers side
  notices the token expiring; connections simply start failing.
- **the notify Lambda** — reads the same secret as `LAKEBASE_URL`, outside the Workers runtime.

```bash
./rotate.sh set storiesLakebaseUrl   # paste postgres://user:token@host:5432/db at the prompt
```

The parser in [`index.ts`](index.ts) (`parseLakebaseOrigin`) validates the URL shape and fails
`pulumi up` with a clear message rather than writing a malformed origin.

**Prefer eliminating this rotation over scheduling it.** A Databricks **service principal** with a
longer-lived credential removes the expiry treadmill entirely; failing that, a scheduled re-apply
(a cron'd `pulumi up` on the deploy-infra workflow) at least keeps the cache fresh. Both features
are dark today (`stories: false`, `contacts: false`), so this is due **before** they go live, not
after.

### `githubWebhookSecret` / `unsubSecret` — Lambda-side, not Pages

Both are AWS Lambda env vars, gated on `notifyEnabled`. They never touch Cloudflare.

- **`githubWebhookSecret`** must be rotated on **both sides simultaneously** — GitHub signs with
  it, the Lambda verifies with it, and neither side supports two values. There is no overlap
  window; webhooks delivered during the swap are rejected, and GitHub will retry them. Update the
  repo webhook's secret and run `pulumi up` back to back.
- **`unsubSecret`** signs unsubscribe links in already-delivered mail. Rotating it **breaks every
  outstanding link** — recipients get an invalid-token error on mail they received before the roll.
  Rotate only on compromise.

### `ASK_PLUGIN_TOKEN` / `COGNITO_CLIENT_SECRET` — wrangler-set

Pulumi does not manage these; they are written straight to Pages and are invisible to
`pulumi stack output`.

```bash
cd web && wrangler pages secret put ASK_PLUGIN_TOKEN
```

`ASK_PLUGIN_TOKEN` is a shared bearer token, so rotating it breaks every configured plugin client
until each is updated — coordinate before rolling. `COGNITO_CLIENT_SECRET` is issued by the
Cognito app client; the client in [`index.ts`](index.ts) is created with `generateSecret: false`
(public PKCE client), so unless that changed there is no such secret to rotate.

## Cadence

Tracked by [`secret-rotation.yml`](../.github/workflows/secret-rotation.yml), which opens a dated
checklist issue on schedule and labels it `area:core` / `type:chore`. The issue *is* the record —
closing it is the attestation that the quarter's rotation happened, and the issue history is the
audit trail. Deliberately **not** a "last rotated" column in this table: a hand-maintained date
column goes stale in one quarter and then lies.

| Secret | Cadence | Why that interval |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | **quarterly** | highest-value credential in the stack — a leak is billable to us at API rates |
| `TURNSTILE_SECRET_KEY` | **quarterly** | shared by both public forms; the two-hour grace window makes it cheap, and rehearsing it keeps the runbook honest |
| `TIPS_APP_PRIVATE_KEY` | **annually** | writes only to this repo's issues, and the App's permissions are already issues-only |
| `HONEYCOMB_API_KEY` | **annually** | write-only telemetry ingest; no user-facing surface |
| `EARLY_ACCESS_SECRET` | **on demand** | rotation *is* the revocation mechanism, not hygiene |
| `storiesLakebaseUrl` | **on token expiry** | driven by Databricks, not by us — see [#1138](https://github.com/watermark-directory/the-watermark-directory/issues/1138) |
| `githubWebhookSecret`, `unsubSecret` | **on compromise** | rotating either has a user-visible cost and no overlap window |
| `CLOUDFLARE_API_TOKEN` | **annually**, and on any operator offboarding | one token holds edit scope over every resource in this stack |

Rotate **immediately**, off-cadence, whenever a value may have been exposed — a key pasted into an
issue or a log, a laptop lost, an operator offboarded.

## Verification

`./rotate.sh verify` runs two independent tiers, because they fail differently:

1. **Project presence** (Cloudflare API) — is the var on the Pages project, and is it typed
   `secret_text`? Catches a `pulumi up` that did not run, wrote to the wrong namespace, or was
   skipped by an `if (secret)` guard in [`index.ts`](index.ts).
2. **Live behaviour** (endpoint probe) — does the *deployed* Function see it? `POST /api/ask` and
   `POST /api/submit` return `500 {"error":"endpoint is misconfigured"}` when a required secret is
   absent, and something else (`400`/`401`/`403`/`503`) when it is present. Anything but that
   specific 500 means the secrets landed. Catches the project-vs-deployment gap — hop 3 of
   [How a rotated value reaches the live Functions](#how-a-rotated-value-reaches-the-live-functions).

Tier 1 green and tier 2 red is the signature of "the value is on the project but the deployment has
not picked it up" — cut a fresh deployment with [`pages.yml`](../.github/workflows/pages.yml)
(`deploy: true`) and re-verify.

Neither tier proves the value is *correct* — only that it is *present*. `--deep` closes that gap
for `ANTHROPIC_API_KEY` alone (a real `/api/ask` round-trip via the plugin bearer token). For
everything else the correctness check is manual and belongs at step 4 of
[The universal ordering](#the-universal-ordering) — before you revoke, never after:

| Secret | Manual correctness check |
| --- | --- |
| `TURNSTILE_SECRET_KEY` | submit the [/submit](https://the.watermark.directory/submit) form; a wrong secret gives `403 verification failed`, not a 500 |
| `TIPS_APP_PRIVATE_KEY` | the same submission actually opens a GitHub issue |
| `HONEYCOMB_API_KEY` | a span from the last few minutes appears in the Honeycomb dataset |
| `storiesLakebaseUrl` | `/api/stories` returns rows rather than 503 |

## Related

- [`README.md`](README.md) — what the stack manages, outputs, bootstrap, CI.
- [`docs/ask-api.md`](../docs/ask-api.md), [`docs/submissions-api.md`](../docs/submissions-api.md) —
  the endpoint contracts, including which env vars each requires.
- [#124](https://github.com/watermark-directory/the-watermark-directory/issues/124) — the
  `ANTHROPIC_API_KEY` provisioning this runbook assumes.
- [#1138](https://github.com/watermark-directory/the-watermark-directory/issues/1138) — the
  Lakebase token-lifetime fix that would retire the `storiesLakebaseUrl` treadmill.
