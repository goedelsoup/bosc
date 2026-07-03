# The submissions seam — tips & corrections

The **submissions endpoint** lets a visitor send a tip or a correction from the public
site. A submission lands as a **labeled, inert GitHub issue** — a *proposal* a human
triages — opened by a narrow GitHub App identity (Epic [#56](https://github.com/watermark-directory/the-watermark-directory/issues/56),
child [#74](https://github.com/watermark-directory/the-watermark-directory/issues/74); the identity pattern follows
the research App, Epic [#57](https://github.com/watermark-directory/the-watermark-directory/issues/57)).

This document **is the contract**: the payload schema, the issue mapping, the abuse
model, and the runtime. It is written so that adding the live endpoint never requires a
redesign — the seam is fixed even where a part is still deferred. See the
[status](#status--whats-live) section for what is live versus stubbed.

> **Chain of custody — a submission is a *proposal*, never evidence.** The corpus under
> `data/documents/**` is litigation evidence; `data/extracted/**` is the reviewed
> artifact. A submission **never** writes to either — it only opens a GitHub issue. The
> endpoint's identity (`bosc-tips-bot`, below) has **Issues: write and nothing else**:
> no Contents access, so there is no code path by which a public form can alter a source
> byte or a reviewed record. Every submission is inert (`needs-triage`) until a
> maintainer acts on it. This mirrors the research App's invariant — the public can
> *propose*; only a human (`@goedelsoup`, via CODEOWNERS) can *act*.

## Architecture

The site is hosted on **Cloudflare Pages**; the endpoint is a **Pages Function**
colocated with the static build, so the form posts **same-origin** (no CORS) and the
App private key lives as a platform secret, never in the browser.

```
                   ┌─ Cloudflare Pages (one origin) ──────────────────────┐
  visitor ───────► │  static Astro build  (web/dist)                 │
                   │                                                       │
  submit form ───► │  POST /api/submit  ──  Pages Function                │
                   │     1. parse + validate payload (schema + size caps) │
                   │     2. verify the Turnstile token (server secret)    │
                   │     3. mint a token for  bosc-tips-bot  (App)        │
                   │     4. POST /repos/.../issues                        │
                   │           labels: submission, needs-triage           │
                   │     5. 200 { issue_url }   (or 4xx with a reason)     │
                   └────────────────────────────┬──────────────────────────┘
                                                │  Issues: write ONLY
                                                ▼
                       GitHub issue ──(inert, human-triaged)──► maintainer
```

The Turnstile token is verified and discarded — never stored, never put in the issue.

## The payload contract

The form sends `POST /api/submit` with a JSON body. The canonical schema is the
TypeScript type + JSON Schema co-located with the Function (`web/functions/api/`),
enforced server-side; this table is its prose source of truth.

| Field | Type | Req. | Notes |
| --- | --- | :---: | --- |
| `kind` | `"tip"` \| `"correction"` \| `"new_source"` | ✓ | A *correction* disputes something on the site; a *new source* points at a document/record we're missing; a *tip* is a new lead. Drives the issue title prefix (`[correction]` / `[new-source]` / `[tip]`). |
| `body` | string | ✓ | The substance. **≤ 4 000 chars.** Rendered into the issue as a fenced block (markdown neutralized — see [abuse](#abuse--spam)). |
| `target` | object | — | What the submission concerns (see [target references](#target-references)). Omitted ⇒ a general submission. |
| `target.ref_kind` | `"record"` \| `"document"` \| `"entity"` \| `"concept"` \| `"page"` \| `"general"` | ✓ if `target` | Which id space `ref_id` lives in. |
| `target.ref_id` | string | ✓ if `target` | The stable id in that space (≤ 300 chars). |
| `target.ref_label` | string | — | The human label as shown on the site (≤ 200 chars), for fast triage. |
| `evidence_url` | string | — | One public URL supporting the claim. Must be `http(s)://`, ≤ 500 chars. Rendered as a link; **not** fetched server-side. |
| `page_url` | string | — | Auto-filled by the form: the site page the submitter was on. Same-origin host only; ≤ 500 chars. |
| `contact` | string | — | Optional submitter contact (email / Signal / …), **for follow-up only**. ≤ 200 chars. Routed to a **private** store and **never** written into the public issue (see [Submitter contact](#submitter-contact--the-private-channel)). |
| `turnstile_token` | string | ✓ | Cloudflare Turnstile token. Verified server-side, then discarded. |

**Anonymous by default; identity stays out of the public issue.** A submission is anonymous
unless the submitter *chooses* to leave a contact, and even then the contact is the **one
field that never reaches the public issue** — for a litigation corpus, identifying detail in
a public issue is a data-handling liability. The body, by contrast, is public; the form tells
submitters to keep private detail out of it and use the contact field instead. See
[Submitter contact](#submitter-contact--the-private-channel) for the private path (#242).

Anything not in this table is **rejected**, not ignored (the validator is allowlist, not
denylist) — so the abuse surface can't grow by a submitter adding fields.

### Submitter contact — the private channel

The optional `contact` is **never** part of the public issue: `buildIssue`/`dedupeInput`
ignore it, so it cannot appear in the title, body, labels, or dedupe marker (asserted by
`submitContact.test.ts`). Instead, **after** the issue is created the handler writes it to a
private Cloudflare KV namespace (`SUBMISSION_CONTACT`), keyed `contact:<issue-number>`, with a
small JSON value (`{ contact, kind, dedupe, deduped, at }`). A maintainer triaging issue `#N`
reads it out-of-band (`wrangler kv key get contact:N`).

- **Retention is bounded** — the KV entry carries a TTL (default **180 days**, overridable via
  `CONTACT_TTL_SEC`), so contact PII expires rather than accumulating.
- **Best-effort, never blocking** — if the `SUBMISSION_CONTACT` namespace isn't bound, or the
  write fails, the submission is still filed (the tip is what matters) and nothing leaks; the
  contact is simply not retained. So the field ships with the seam but only *retains* contact
  once an operator binds the KV at go-live.

### Target references

A submission can point at something concrete so triage is fast. `ref_id` is the **stable
id already used inside the content bundle** — no new id space is invented:

| `ref_kind` | `ref_id` is… | Source of truth |
| --- | --- | --- |
| `record` | the record `rel` (path under `data/extracted`, e.g. `aedg/roundabouts.summary.opc.yaml`) | `RecordItem.rel` ([feeds.py](../src/watermark/site/feeds.py)) |
| `document` | the document's repo-relative path under `data/documents` | the documents feed |
| `entity` | the canonical entity `key` | `EntityNode.key` |
| `concept` | the concept `slug` | `ConceptItem.slug` |
| `page` | a site path (`/site/records/opc`, …) | the site itself |
| `general` | *(empty)* | — |

The form fills `target` automatically when a "suggest a correction" affordance is placed
on a record/entity/concept page (it already knows the id it rendered); the standalone
`/submit` page leaves it `general` unless the submitter pastes a link.

### Example

```jsonc
{
  "kind": "correction",
  "target": {
    "ref_kind": "record",
    "ref_id": "aedg/roundabouts.summary.opc.yaml",
    "ref_label": "Roundabouts OPC — summary"
  },
  "body": "The ROADWAY subtotal on sheet 3 reads $1.2M but the detail pages sum to $1.18M.",
  "evidence_url": "https://example.gov/some-public-record.pdf",
  "page_url": "https://<host>/site/records/opc",
  "turnstile_token": "<verified server-side, then dropped>"
}
```

## How a submission becomes an issue

| Issue part | Derived from |
| --- | --- |
| **title** | `[tip]` / `[correction]` + `ref_label` (or the first ~60 chars of `body` when untargeted) |
| **body** | a structured block: the target (kind + a deep link to `page_url`), the submission text as a **fenced quote**, the `evidence_url` as a link, and a provenance footer (*"Submitted via the public form; Turnstile-verified; **unverified** — triage before acting."*) |
| **labels** | `submission` (provenance marker — opened via the public form) + `needs-triage` (inert until a human acts) |
| **dedupe** | a hidden marker `<!-- submission: <sha256(ref + normalized body)> -->`. Before creating, the Function scans the open `submission` issues for this marker and returns the existing one instead of a duplicate (see [Abuse & spam](#abuse--spam)). |

The provenance label is to submissions what `agent-proposed` is to research proposals,
and `needs-triage` is shared — so the existing triage habit covers both. Both labels are
[Pulumi-managed](../.github/config/index.ts) (`submission` is added to `runtimeLabels`).

## Abuse & spam

The endpoint opens public issues, so it is an abuse vector. Controls, interim → hardened:

**Built into the endpoint:**

- **Cloudflare Turnstile** — a human-verification token required on every submission,
  verified server-side against the Turnstile secret. The first line of defense.
- **Per-IP rate limiting** (Phase 5) — a fixed-window KV counter (default **5 per IP per
  hour**, `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SEC`) checked *before* Turnstile, so a
  flooding IP is cut off cheaply; over-limit gets `429` + `Retry-After`. **Opt-in and
  fail-open:** with no `RATE_LIMIT` KV namespace bound it's simply off, and a KV error
  allows the request (Turnstile stays the primary gate). KV is eventually consistent, so
  this is a soft dampener, not a hard cap.
- **Dedupe** (Phase 5) — before creating, the Function scans the open `submission` issues
  for the same `<!-- submission: <hash> -->` marker and returns that existing issue
  (`200 {deduped:true}`) instead of opening a duplicate. Best-effort (first 100 open
  submissions; errors fail open to *create*, never drop). The triage queue stays bounded
  because handled issues are closed (leave `state=open`).
- **Hard size caps** — per the schema table; oversized or malformed bodies are rejected
  `4xx` before any GitHub call.
- **Markdown neutralized** — `body` is emitted inside a fenced block and the title is
  plain-text, so a submission can't inject markdown/HTML or forge the provenance footer.
  `evidence_url`/`page_url` are scheme-checked (`http(s)` only) and `page_url` must be
  the site's own host.
- **GitHub's own per-token issue rate limits** backstop volume.

The KV namespace + Turnstile widget can be **Pulumi-managed** via the dedicated
[`deploy/`](../deploy/) stack (`@pulumi/cloudflare`) — set `cloudflareAccountId` and it
provisions them and exports the id + keys to wire in (see [`deploy/README.md`](../deploy/README.md)).
The Pages **project** stays wrangler-deployed (managing its config in two tools would
drift).

**Still deferred:** optional notify-on-submit.

**Triage** the queue with this saved filter — open submissions awaiting a human:
<https://github.com/watermark-directory/the-watermark-directory/issues?q=is%3Aopen+is%3Aissue+label%3Asubmission+label%3Aneeds-triage>.
Closing an issue (or dropping `needs-triage`) takes it off the queue and out of dedupe's
open-issue scan. The moderation model is the same as everywhere in BOSC: nothing a
non-maintainer produces is acted on automatically — it sits labeled and inert until
`@goedelsoup` triages it.

## Identity — the `bosc-tips-bot` App

A **second, narrower** GitHub App than the research bot. The research App needs
Contents: write (it pushes a branch); the submissions endpoint only opens an issue, so
its identity is strictly smaller — least privilege, and a compromise of the edge
function cannot reach the code tree.

| Permission | Access | Why |
| --- | --- | --- |
| Issues | Read & write | open the submission issue (read is for the deferred dedupe list) |
| Metadata | Read | mandatory baseline |

Everything else **No access** — no Contents, no Pull requests, no Administration. The App
is not a code owner and not a repo admin, so branch protection binds it just as it binds
the research App. Tips are also *visibly distinct* from research proposals in the issue
stream because they come from a different identity.

## Runtime & deploy

- **Function:** `web/functions/api/submit.ts` — a Cloudflare Pages Function, routed
  to `/api/submit` because `functions/` sits at the deployed project root (Cloudflare
  Pages points at `web/`; the Astro `dist/` is the static half).
- **Form:** a framework-free affordance (vanilla client script + the Turnstile widget,
  in the zero-React style of `src/scripts/search.ts`) — a standalone `/submit` page plus
  an inline "suggest a correction" control on record/entity/concept pages that pre-fills
  `target`. A no-JS fallback states the endpoint needs JavaScript (Turnstile requires
  it) and links to opening a GitHub issue manually.
- **Build:** unchanged from the host migration — GitHub Actions runs `watermark export` →
  `npm run build` (the Python bundle step stays where uv caching works), then deploys
  `web/dist` **and** `web/functions/` to Cloudflare Pages via Wrangler. This
  supersedes the GitHub Pages flip ([#102](https://github.com/watermark-directory/the-watermark-directory/issues/102)/[#107](https://github.com/watermark-directory/the-watermark-directory/issues/107)).

### Environment

| Name | Where | What |
| --- | --- | --- |
| `TIPS_APP_ID` | Cloudflare (Function secret) | the `bosc-tips-bot` App ID |
| `TIPS_APP_PRIVATE_KEY` | Cloudflare (Function secret) | the App's private key, **PKCS#8** (see note) |
| `TURNSTILE_SECRET_KEY` | Cloudflare (Function secret) | server-side Turnstile verification |
| `PUBLIC_TURNSTILE_SITE_KEY` | GitHub Actions **build** var (wired into `pages.yml`) | the Turnstile widget's public site key — read at build time by `submit.astro`, so it must be in the build env, not just a Function secret |
| `SUBMISSIONS_ENABLED` | Cloudflare (Function var) | on / kill switch — anything but `true` ⇒ the endpoint returns `503` and the form shows disabled |
| `SUBMISSION_CONTACT` | Cloudflare (KV binding) | the **private** submitter-contact store (#242), keyed `contact:<issue-number>`. Optional — absent ⇒ the contact field is accepted but not retained (never leaked). |
| `CONTACT_TTL_SEC` | Cloudflare (Function var) | optional override for contact retention (seconds); default 180 days |

The research App's key stays only in GitHub Actions; the tips App's key lives only in
Cloudflare. One identity per runtime, neither broader than its job.

The deployment infrastructure (the Turnstile widget + rate-limit KV, and the
Route53↔Cloudflare custom-domain exchange) is managed by the [`deploy/`](../deploy/) Pulumi
stack — state in a self-managed **S3** backend, secrets via **awskms**, AWS auth via an
**OIDC** role. See [`deploy/README.md`](../deploy/README.md).

## Bootstrap (one-time)

Nothing is live until these steps are done: until then the endpoint returns `503`
(`SUBMISSIONS_ENABLED` unset) and the form shows a disabled placeholder
(`PUBLIC_TURNSTILE_SITE_KEY` unset). Steps are grouped by phase. The GitHub-App half
(Phase 4a) is independent of the host; the Cloudflare secrets (4b) can only be set once
the Pages project exists (Phase 1).

### Phase 4a — register `bosc-tips-bot` (GitHub; host-independent)

1. GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**.
   - **Webhook:** uncheck *Active* (the Function calls the REST API directly; no webhook).
   - **Permissions:** **Issues — Read & write** and **Metadata — Read**, nothing else
     (no Contents, so it can never touch the corpus).
   - **Where can this App be installed?** Only on this account; install on
     `watermark-directory/the-watermark-directory` only.
2. Note the **App ID**; generate and download a **private key**. GitHub issues a PKCS#1
   key (`-----BEGIN RSA PRIVATE KEY-----`); Web Crypto needs **PKCS#8** — convert once:

   ```sh
   openssl pkcs8 -topk8 -nocrypt -in tips-app.pem -out tips-app.pkcs8.pem
   ```

   The PKCS#8 contents become `TIPS_APP_PRIVATE_KEY` (step 6).
3. `pulumi up` to create the **`submission`** label (declared in
   [`.github/config`](../.github/config/index.ts); `needs-triage` already exists).

### Phase 1 — the host (prerequisite for the Cloudflare secrets)

4. Create a **Cloudflare Pages** project named **`bosc`** (production branch `main`). The
   Wrangler direct-upload deploy is wired in [`pages.yml`](../.github/workflows/pages.yml)
   (manual, build-only by default) — config in [`web/wrangler.toml`](../web/wrangler.toml).
   Set two repo **secrets**: `CLOUDFLARE_API_TOKEN` (a token with *Cloudflare Pages —
   Edit*) and `CLOUDFLARE_ACCOUNT_ID`. The default domain is `watermark.pages.dev` at the
   root (no base path).

   **Custom domain (decided: a subdomain on Route53).** Set `siteDomain` + `route53ZoneId`
   in the [`deploy/`](../deploy/) stack and `pulumi up` — Pulumi attaches the domain to the
   Pages project (`cloudflare.PagesDomain`) **and** creates the Route53 CNAME →
   `watermark.pages.dev`, then Cloudflare validates and issues the cert. Set the repo var
   `PAGES_SITE_URL` to the `siteUrl` output so the build emits absolute links (no code
   change). A bare apex isn't used — it can't point cross-provider at pages.dev.
5. Create a free **Turnstile** widget for that domain; note the **site key** (public)
   and **secret key**. (Or let Pulumi create it via the [`deploy/`](../deploy/) stack and
   read the keys from its stack outputs.)

### Phase 4b — wire the secrets (once the Pages project exists)

6. Cloudflare Pages project → Settings → environment variables, for the production env:
   `TIPS_APP_ID`, `TIPS_APP_PRIVATE_KEY` (PKCS#8 contents) and `TURNSTILE_SECRET_KEY` as
   **secrets**; `SUBMISSIONS_ENABLED=true` as a plain var (the kill switch).
7. In the **frontend build env** (the Actions deploy step / Pages build settings) set
   `PUBLIC_TURNSTILE_SITE_KEY` to the Turnstile site key, and rebuild so the live form
   renders in place of the placeholder.

### Verify

8. **Dry-run with Turnstile test keys first** (they never involve a real human): site key
   `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA` (always
   pass; the secret `2x0000000000000000000000000000000AA` always fails — use it to
   confirm the `403` path). With the always-pass secret set, post a submission:

   ```sh
   curl -sS -X POST https://<host>/api/submit \
     -H 'content-type: application/json' \
     -d '{"kind":"tip","body":"bootstrap test — please close","turnstile_token":"dummy"}'
   ```

   Expect `201 {"issue_url": …}` and a new `submission` + `needs-triage` issue opened by
   `bosc-tips-bot[bot]`. Close the test issue, then swap in the **real** Turnstile keys.

### Optional — enable per-IP rate limiting (Phase 5)

Rate limiting is off until a KV namespace is bound. To enable it, create one and wire the
`RATE_LIMIT` binding in [`web/wrangler.toml`](../web/wrangler.toml):

```sh
npx wrangler kv namespace create RATE_LIMIT   # prints the namespace id
```

(Or have Pulumi create the namespace via the [`deploy/`](../deploy/) stack and use its
`rateLimitKvNamespaceId` stack output as the id.)

Uncomment the `[[kv_namespaces]]` block with that id, then redeploy. Override the
defaults (5 / 3600s) with the `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SEC` vars if needed.

### Turning it off

Set `SUBMISSIONS_ENABLED` to anything but `true` (the endpoint returns `503`; the form
shows the placeholder on the next build), or uninstall the App.

## Local testing

Two ways to exercise this endpoint locally without filing a real issue, both detailed in
[`web/README.md`](../web/README.md) → *Local dev & testing*:

- **Automated:** `src/lib/submitRoute.test.ts` drives `onRequestPost` end-to-end (kill
  switch → validation → rate-limit → Turnstile → App-JWT → dedupe → issue → contact store)
  with a stubbed `fetch`, under `npm test`. No network, no issue filed.
- **Interactive:** `mise run //web:dev:stack` serves the form + endpoint under
  `wrangler pages dev`; the GitHub API is mocked (`scripts/dev-mocks.mjs` via
  `GITHUB_API_BASE`), Turnstile uses the always-pass dummy keys, so a submission opens a
  *mock* issue only.

## Status — what's live

| Part | State |
| --- | --- |
| This contract (schema, mapping, abuse model, identity) | **defined** (#74) |
| Interim endpoint (`web/functions/api/submit.ts`: Turnstile + create issue) | **built** — dormant until bootstrapped (`SUBMISSIONS_ENABLED`) |
| Frontend form (`/submit`) + query-param `target` pre-fill | **built** — disabled placeholder until `PUBLIC_TURNSTILE_SITE_KEY` is set |
| `submission` label (Pulumi) | **coded** (Phase 4 — `pulumi up` to apply) |
| Cloudflare Pages host migration | **wired** (Phase 1 — `pages.yml` Wrangler deploy + `wrangler.toml`; needs the CF project + `CLOUDFLARE_*` secrets) |
| `bosc-tips-bot` App + secrets | planned (Phase 4 — manual bootstrap, below) |
| Per-IP rate limit + dedupe + triage filter | **built** (Phase 5 — rate limit opt-in via a `RATE_LIMIT` KV binding) |
| Pulumi-managed CF resources (KV namespace + Turnstile) | **built** ([`deploy/`](../deploy/) stack — opt-in) |
| Notify-on-submit | **deferred** |
| Webhook receiver (event-driven, Epic 4 upgrade) | **deferred** — the Function is the request-driven seam; a persistent receiver is a later tier |

### Settled decisions (#240)

- **Domain** — a **custom subdomain on Route53**, CNAME → `watermark.pages.dev`, attached to the
  Pages project via Pulumi (`cloudflare.PagesDomain` + `aws.route53.Record`). The exact
  name is late-bound (one `pulumi config set siteDomain …`); a bare apex is not used
  (illegal cross-provider CNAME / ALIAS).
- **Infra state + auth** — Pulumi state in a self-managed **S3** backend (no SaaS), secrets
  via **awskms**, the `deploy-infra` CI assuming an AWS **OIDC** role.
- **Target granularity** — the per-page `target` pre-fill is **already wired** (the "✎
  Suggest a correction" deep-links across record/entity/concept/people/places); not
  `general`-only.
- **Submitter contact** — still **none** in the public path; a private intake channel is
  tracked separately in [#242](https://github.com/watermark-directory/the-watermark-directory/issues/242), and
  file-attach in [#243](https://github.com/watermark-directory/the-watermark-directory/issues/243).
