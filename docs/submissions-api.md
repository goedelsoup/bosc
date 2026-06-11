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
| **dedupe** | a hidden marker `<!-- submission: <sha256(ref + normalized body)> -->`, so a resubmit is detectable. Listing/deduping against open issues is a Phase-5 hardening (the marker is written now so it's free later). |

The provenance label is to submissions what `agent-proposed` is to research proposals,
and `needs-triage` is shared — so the existing triage habit covers both. Both labels are
[Pulumi-managed](../.github/config/index.ts) (`submission` is added to `runtimeLabels`).

## Abuse & spam

The endpoint opens public issues, so it is an abuse vector. Controls, interim → hardened:

**Live in the interim endpoint:**
- **Cloudflare Turnstile** — a human-verification token required on every submission,
  verified server-side against the Turnstile secret. The first line of defense.
- **Hard size caps** — per the schema table; oversized or malformed bodies are rejected
  `4xx` before any GitHub call.
- **Markdown neutralized** — `body` is emitted inside a fenced block and the title is
  plain-text, so a submission can't inject markdown/HTML or forge the provenance footer.
  `evidence_url`/`page_url` are scheme-checked (`http(s)` only) and `page_url` must be
  the site's own host.
- **GitHub's own per-token issue rate limits** backstop volume.

**Phase-5 hardening (deferred, the seam is ready):**
- **Per-IP / per-window rate limiting** via Cloudflare KV (or Durable Objects) — the
  interim relies on Turnstile + GitHub limits; a KV counter is the next increment.
- **Dedupe** against open `submission` issues using the marker above (needs an
  Issues: read list per submit — a soft cost, hence deferred).
- **A triage surface** (a saved filter / lightweight view over `label:submission
  label:needs-triage`), and optional notify-on-submit.

The moderation model is the same as everywhere in BOSC: nothing a non-maintainer
produces is acted on automatically — it sits labeled and inert until `@goedelsoup`
triages it.

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
| `TIPS_APP_PRIVATE_KEY` | Cloudflare (Function secret) | the App's `.pem` private key |
| `TURNSTILE_SECRET_KEY` | Cloudflare (Function secret) | server-side Turnstile verification |
| `PUBLIC_TURNSTILE_SITE_KEY` | frontend build env | the Turnstile widget's public site key |
| `SUBMISSIONS_ENABLED` | Cloudflare (Function var) | on / kill switch — anything but `true` ⇒ the endpoint returns `503` and the form shows disabled |

The research App's key stays only in GitHub Actions; the tips App's key lives only in
Cloudflare. One identity per runtime, neither broader than its job.

## Bootstrap (one-time)

Like the research App, none of this is live until the steps are done; until then the
form is disabled (`SUBMISSIONS_ENABLED` unset) and shows a placeholder.

1. **Register `bosc-tips-bot`** — GitHub → Settings → Developer settings → GitHub Apps →
   New. Webhook **off** (the Function calls the REST API directly; no webhook server).
   Permissions: the two rows above, nothing more. Install on `goedelsoup/bosc` only.
   Note the App ID; generate and download the private key.
2. **Cloudflare Pages** — create a Pages project pointed at this repo's `frontend/`
   build output (or wire the Wrangler deploy step in Actions). Add a custom domain or
   use the `*.pages.dev` subdomain; set the Astro `SITE_URL`/`BASE_PATH` to match (a root
   domain drops the `/bosc` base path).
3. **Turnstile** — create a Turnstile widget (free) for the site's domain; note the site
   key (public) and secret key.
4. **Secrets & vars** — set the five environment entries above (App id/key + Turnstile
   secret + `SUBMISSIONS_ENABLED=true` in Cloudflare; the Turnstile **site** key in the
   frontend build env).
5. **Labels** — `pulumi up` to create the `submission` label (added to
   [`.github/config`](../.github/config/index.ts) alongside the research labels).

## Status — what's live

| Part | State |
| --- | --- |
| This contract (schema, mapping, abuse model, identity) | **defined** (#74) |
| Cloudflare Pages host migration | planned (supersedes the GitHub Pages flip) |
| Interim live endpoint (Turnstile + create issue) | planned |
| Frontend form + `target` pre-fill | planned |
| KV rate-limit, dedupe, triage surface | **deferred** (Phase 5 — seam is ready) |
| Webhook receiver (event-driven, Epic 4 upgrade) | **deferred** — the Function is the request-driven seam; a persistent receiver is a later tier |

### Open decisions

- **Domain** — `*.pages.dev` vs a custom domain (affects `base`, links, Turnstile host).
- **Target granularity** — ship `general`-only first, or wire the per-page `target`
  pre-fill from the start (more useful, a little more form code).
- **Submitter contact** — defaulted to **none** above; only revisit with a non-public
  intake path.
