# The submissions seam — tips & corrections

The **submissions endpoint** lets a visitor send a tip or a correction from the public
site. A submission lands as a **labeled, inert GitHub issue** — a *proposal* a human
triages — opened by a narrow GitHub App identity (Epic [#56](https://github.com/goedelsoup/bosc/issues/56),
child [#74](https://github.com/goedelsoup/bosc/issues/74); the identity pattern follows
the research App, Epic [#57](https://github.com/goedelsoup/bosc/issues/57)).

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
  visitor ───────► │  static Astro build  (frontend/dist)                 │
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
TypeScript type + JSON Schema co-located with the Function (`frontend/functions/api/`),
enforced server-side; this table is its prose source of truth.

| Field | Type | Req. | Notes |
| --- | --- | :---: | --- |
| `kind` | `"tip"` \| `"correction"` | ✓ | A *correction* disputes something on the site; a *tip* is a new lead. Drives the issue title prefix. |
| `body` | string | ✓ | The substance. **≤ 4 000 chars.** Rendered into the issue as a fenced block (markdown neutralized — see [abuse](#abuse--spam)). |
| `target` | object | — | What the submission concerns (see [target references](#target-references)). Omitted ⇒ a general submission. |
| `target.ref_kind` | `"record"` \| `"document"` \| `"entity"` \| `"concept"` \| `"page"` \| `"general"` | ✓ if `target` | Which id space `ref_id` lives in. |
| `target.ref_id` | string | ✓ if `target` | The stable id in that space (≤ 300 chars). |
| `target.ref_label` | string | — | The human label as shown on the site (≤ 200 chars), for fast triage. |
| `evidence_url` | string | — | One public URL supporting the claim. Must be `http(s)://`, ≤ 500 chars. Rendered as a link; **not** fetched server-side. |
| `page_url` | string | — | Auto-filled by the form: the site page the submitter was on. Same-origin host only; ≤ 500 chars. |
| `turnstile_token` | string | ✓ | Cloudflare Turnstile token. Verified server-side, then discarded. |

**No submitter identity field — by design.** The endpoint is anonymous; there is no
name/email/contact field. For a litigation corpus, an optional contact in a *public*
issue is a data-handling liability, and "anonymous" should mean anonymous. Follow-up, if
any, happens in the public issue thread. (This is a deliberate default; revisit only
with an explicit decision and a non-public intake path.)

Anything not in this table is **rejected**, not ignored (the validator is allowlist, not
denylist) — so the abuse surface can't grow by a submitter adding fields.

### Target references

A submission can point at something concrete so triage is fast. `ref_id` is the **stable
id already used inside the content bundle** — no new id space is invented:

| `ref_kind` | `ref_id` is… | Source of truth |
| --- | --- | --- |
| `record` | the record `rel` (path under `data/extracted`, e.g. `aedg/roundabouts.summary.opc.yaml`) | `RecordItem.rel` ([feeds.py](../src/bosc/site/feeds.py)) |
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

**Still deferred:** optional notify-on-submit, and Pulumi-managing the Cloudflare
resources (Pages project + KV namespace) via `@pulumi/cloudflare` (today they're created
in the dashboard / via `wrangler`).

**Triage** the queue with this saved filter — open submissions awaiting a human:
<https://github.com/goedelsoup/bosc/issues?q=is%3Aopen+is%3Aissue+label%3Asubmission+label%3Aneeds-triage>.
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

- **Function:** `frontend/functions/api/submit.ts` — a Cloudflare Pages Function, routed
  to `/api/submit` because `functions/` sits at the deployed project root (Cloudflare
  Pages points at `frontend/`; the Astro `dist/` is the static half).
- **Form:** a framework-free affordance (vanilla client script + the Turnstile widget,
  in the zero-React style of `src/scripts/search.ts`) — a standalone `/submit` page plus
  an inline "suggest a correction" control on record/entity/concept pages that pre-fills
  `target`. A no-JS fallback states the endpoint needs JavaScript (Turnstile requires
  it) and links to opening a GitHub issue manually.
- **Build:** unchanged from the host migration — GitHub Actions runs `bosc export` →
  `npm run build` (the Python bundle step stays where uv caching works), then deploys
  `frontend/dist` **and** `frontend/functions/` to Cloudflare Pages via Wrangler. This
  supersedes the GitHub Pages flip ([#102](https://github.com/goedelsoup/bosc/issues/102)/[#107](https://github.com/goedelsoup/bosc/issues/107));
  `bosc site build` remains the local fallback.

### Environment

| Name | Where | What |
| --- | --- | --- |
| `TIPS_APP_ID` | Cloudflare (Function secret) | the `bosc-tips-bot` App ID |
| `TIPS_APP_PRIVATE_KEY` | Cloudflare (Function secret) | the App's private key, **PKCS#8** (see note) |
| `TURNSTILE_SECRET_KEY` | Cloudflare (Function secret) | server-side Turnstile verification |
| `PUBLIC_TURNSTILE_SITE_KEY` | frontend build env | the Turnstile widget's public site key |
| `SUBMISSIONS_ENABLED` | Cloudflare (Function var) | on / kill switch — anything but `true` ⇒ the endpoint returns `503` and the form shows disabled |

The research App's key stays only in GitHub Actions; the tips App's key lives only in
Cloudflare. One identity per runtime, neither broader than its job.

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
     `goedelsoup/bosc` only.
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
   (manual, build-only by default) — config in [`frontend/wrangler.toml`](../frontend/wrangler.toml).
   Set two repo **secrets**: `CLOUDFLARE_API_TOKEN` (a token with *Cloudflare Pages —
   Edit*) and `CLOUDFLARE_ACCOUNT_ID`. The default domain is `bosc.pages.dev` at the
   root (no base path); for a custom domain set the repo vars `PAGES_SITE_URL` /
   `PAGES_BASE_PATH` (no code change).
5. Create a free **Turnstile** widget for that domain; note the **site key** (public)
   and **secret key**.

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
`RATE_LIMIT` binding in [`frontend/wrangler.toml`](../frontend/wrangler.toml):

```sh
npx wrangler kv namespace create RATE_LIMIT   # prints the namespace id
```

Uncomment the `[[kv_namespaces]]` block with that id, then redeploy. Override the
defaults (5 / 3600s) with the `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SEC` vars if needed.

### Turning it off

Set `SUBMISSIONS_ENABLED` to anything but `true` (the endpoint returns `503`; the form
shows the placeholder on the next build), or uninstall the App.

## Status — what's live

| Part | State |
| --- | --- |
| This contract (schema, mapping, abuse model, identity) | **defined** (#74) |
| Interim endpoint (`frontend/functions/api/submit.ts`: Turnstile + create issue) | **built** — dormant until bootstrapped (`SUBMISSIONS_ENABLED`) |
| Frontend form (`/submit`) + query-param `target` pre-fill | **built** — disabled placeholder until `PUBLIC_TURNSTILE_SITE_KEY` is set |
| `submission` label (Pulumi) | **coded** (Phase 4 — `pulumi up` to apply) |
| Cloudflare Pages host migration | **wired** (Phase 1 — `pages.yml` Wrangler deploy + `wrangler.toml`; needs the CF project + `CLOUDFLARE_*` secrets) |
| `bosc-tips-bot` App + secrets | planned (Phase 4 — manual bootstrap, below) |
| Per-IP rate limit + dedupe + triage filter | **built** (Phase 5 — rate limit opt-in via a `RATE_LIMIT` KV binding) |
| Notify-on-submit; Pulumi-managed CF resources (`@pulumi/cloudflare`) | **deferred** |
| Webhook receiver (event-driven, Epic 4 upgrade) | **deferred** — the Function is the request-driven seam; a persistent receiver is a later tier |

### Open decisions

- **Domain** — `*.pages.dev` vs a custom domain (affects `base`, links, Turnstile host).
- **Target granularity** — ship `general`-only first, or wire the per-page `target`
  pre-fill from the start (more useful, a little more form code).
- **Submitter contact** — defaulted to **none** above; only revisit with a non-public
  intake path.
