# Auth — Cognito identity foundation (Epic #919)

**Status:** design (Epic #919, as of 2026-07-02) — describes the *planned* identity
foundation; not yet built. The present-tense below is the target design, not a live system.

Watermark Directory uses **AWS Cognito** as its identity provider. The Hosted UI
handles registration, email verification, password reset, and social OAuth. The
platform uses a **PKCE Authorization Code** flow — no implicit grant.

## Architecture

```
Browser                   Cloudflare Pages          AWS Cognito
  |                              |                      |
  |-- GET /account/login ------->|                      |
  |   (generates PKCE, stores    |                      |
  |    code_verifier in          |                      |
  |    sessionStorage)           |                      |
  |                              |                      |
  |-- redirect ─────────────────────────────────────>  |
  |   /oauth2/authorize          |                      |
  |   ?code_challenge=S256       |                      |
  |                              |                      |
  |<─ redirect ─────────────────────────────────────   |
  |   /account/callback?code=…   |                      |
  |                              |                      |
  |-- POST /api/account/token -->|                      |
  |   { code, code_verifier }    |-- POST /oauth2/token ->|
  |                              |<── { id_token, … } ─   |
  |<── { id_token, … } ---------| (sets __rt cookie)   |
  |    stores id_token in        |                      |
  |    sessionStorage            |                      |
```

**Token storage:**

- `id_token` → `sessionStorage` (cleared on tab close; JS-readable for display)
- `refresh_token` → `HttpOnly Secure SameSite=Lax` cookie (server-managed; JS
  cannot read it; scoped to `Path=/api/account`)

## Three roles

Roles flow from **Cognito User Pool Groups** into the ID token as the
`cognito:groups` claim. The `_lib/auth.ts` `extractRole()` helper picks the
highest-privilege group:

| Group | Role string | Who |
|-------|------------|-----|
| `admin` | `"admin"` | Platform-wide admins |
| `site-admin` | `"site-admin"` | Per-site curators; site slugs in `custom:admin_sites` |
| *(none)* | `"standard"` | Authenticated general users |

## Provisioning (A1) — AWS steps

Run these once per environment. A Terraform module will be added in a follow-up
(#920); until then, use the AWS console / CLI.

### 1. Create the User Pool

```bash
aws cognito-idp create-user-pool \
  --pool-name watermark-prod \
  --auto-verified-attributes email \
  --username-attributes email \
  --schema '[
    {"Name":"email","Required":true,"Mutable":true},
    {"Name":"admin_sites","AttributeDataType":"String","Mutable":true}
  ]' \
  --region us-east-1
```

Note the `UserPoolId` (e.g. `us-east-1_XXXXXXXXX`).

### 2. Create the Hosted UI domain

```bash
aws cognito-idp create-user-pool-domain \
  --domain watermark-auth \
  --user-pool-id <POOL_ID> \
  --region us-east-1
# → Hosted UI at: watermark-auth.auth.us-east-1.amazoncognito.com
# OR use a custom domain (requires ACM cert in us-east-1).
```

### 3. Create an App Client

In the console (App clients → Create): pick **Public client**, enable
**Authorization code grant** + **S256 PKCE**. Callback URLs:

- `https://watermarkdirectory.org/account/callback`
- `http://localhost:4321/account/callback` (local dev)

Sign-out URLs: `https://watermarkdirectory.org/`, `http://localhost:4321/`.

Scopes: `openid email profile`.

Note the **Client ID** (no secret for a public client; if you choose a
confidential client, set `COGNITO_CLIENT_SECRET` as a dashboard secret).

### 4. Create User Pool Groups

```bash
for group in standard site-admin admin; do
  aws cognito-idp create-group \
    --group-name $group \
    --user-pool-id <POOL_ID> \
    --region us-east-1
done
```

### 5. Social providers (optional — add later)

Configure Google / GitHub / Facebook in the console under **Federated identity
providers**, then add them to the app client's **Enabled identity providers**.

## Configuration

### Dashboard secrets (never in wrangler.toml)

| Secret | Description |
|--------|-------------|
| `COGNITO_CLIENT_SECRET` | App client secret (confidential client only) |

### Vars — add to wrangler.toml `[vars]` once provisioned

```toml
AUTH_ENABLED = "true"
COGNITO_REGION = "us-east-1"
COGNITO_USER_POOL_ID = "us-east-1_XXXXXXXXX"
COGNITO_CLIENT_ID = "<app-client-id>"
COGNITO_DOMAIN = "watermark-auth.auth.us-east-1.amazoncognito.com"
APP_BASE_URL = "https://watermarkdirectory.org"
```

### CI build env (non-secrets baked into the Astro build)

These must be set in the GitHub Actions build environment (`.github/workflows/pages.yml`)
and in the Cloudflare Pages build settings so the `PUBLIC_*` vars are available
at `pnpm run build` time:

```bash
PUBLIC_COGNITO_DOMAIN=watermark-auth.auth.us-east-1.amazoncognito.com
PUBLIC_COGNITO_CLIENT_ID=<app-client-id>
```

These are safe to set in the build environment (not secrets) — Cognito client IDs
are public identifiers, similar to a Turnstile site key.

### KV namespace

Create the JWKS cache namespace and add it to wrangler.toml:

```bash
npx wrangler kv namespace create JWKS_CACHE
# → prints: id = "abc123..."
```

Then uncomment and fill in the `[[kv_namespaces]]` stub in `wrangler.toml`.

## Go-live checklist

- [ ] User Pool created; `COGNITO_USER_POOL_ID` + `COGNITO_REGION` noted
- [ ] Hosted UI domain configured; `COGNITO_DOMAIN` noted
- [ ] App client created (PKCE, correct callback + logout URLs); `COGNITO_CLIENT_ID` noted
- [ ] Three groups created: `standard`, `site-admin`, `admin`
- [ ] `JWKS_CACHE` KV namespace created and wired in wrangler.toml
- [ ] `AUTH_ENABLED`, `COGNITO_*`, `APP_BASE_URL` set in wrangler.toml `[vars]`
- [ ] `PUBLIC_COGNITO_DOMAIN` and `PUBLIC_COGNITO_CLIENT_ID` set in CI + Cloudflare build settings
- [ ] Deployed; `/account/login` redirects to the Hosted UI
- [ ] Test full round-trip: login → callback → sessionStorage id_token present → sign out → cleared

## Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/account/login` | GET | Generates PKCE, redirects to Cognito Hosted UI |
| `/account/callback` | GET | Exchanges `code` + verifier; stores tokens |
| `/account/logout` | GET | Clears tokens; ends Cognito Hosted UI session |
| `/api/account/token` | POST | Server: exchanges code → tokens; sets `__rt` cookie |
| `/api/account/refresh` | POST | Server: uses `__rt` cookie → new id_token |
| `/api/account/logout` | POST | Server: clears `__rt` cookie |

## Local dev

Set these in `web/.dev.vars` (gitignored):

```ini
AUTH_ENABLED=true
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=<app-client-id>
COGNITO_DOMAIN=watermark-auth.auth.us-east-1.amazoncognito.com
APP_BASE_URL=http://localhost:4321
```

And in `web/.env` (gitignored; read by Vite/Astro at build time):

```ini
PUBLIC_COGNITO_DOMAIN=watermark-auth.auth.us-east-1.amazoncognito.com
PUBLIC_COGNITO_CLIENT_ID=<app-client-id>
```

Run the full stack: `mise run //web:dev:stack` (wrangler + Astro dev server).
