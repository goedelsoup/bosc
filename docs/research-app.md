# The research GitHub App — bootstrap

The automated-research bot (Epic [#57](https://github.com/goedelsoup/bosc/issues/57))
is a **GitHub App** identity that drives `bosc research run` over the corpus and opens
a PR + proposed issues *as the App*. This is the one-time setup. None of it runs until
you finish it — the [`research.yml`](../.github/workflows/research.yml) workflow is
gated on the `RESEARCH_ENABLED` variable, so every run is **skipped** (not failed)
until you opt in.

> **Chain of custody.** A run is read-only on `data/documents/**` (the workflow has a
> hard check that aborts if any source byte changed), and the App **cannot approve or
> merge its own PR**: `main` requires one approving review *and* a
> [CODEOWNERS](../.github/CODEOWNERS) review (`@goedelsoup`), and the App is neither a
> code owner nor a repo admin. A human verifies every run before anything is acted on.

## 1. Register the App

GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**.

- **Name:** e.g. `bosc-research-bot`.
- **Homepage URL:** the repo URL is fine.
- **Webhook:** **uncheck Active** — there is no webhook server yet (runs are driven by
  Actions: cron + manual dispatch + the `/research` slash command). This is the planned
  upgrade path and ties into Epic 4.
- **Repository permissions (least privilege — nothing broader):**

  | Permission | Access | Why |
  | --- | --- | --- |
  | Contents | Read & write | push the run branch (`data/research/**` only) |
  | Pull requests | Read & write | open the research PR |
  | Issues | Read & write | open the proposed issues; list open ones to dedupe |
  | Metadata | Read | mandatory baseline |

  Leave everything else **No access**. In particular the App gets **no Administration
  access**, so branch protection binds it and it cannot self-merge.

- **Where can this App be installed?** Only on this account.

Create the App, then note its **App ID** and **generate a private key** (downloads a
`.pem`).

## 2. Install the App on the repo

From the App's page → **Install App** → install on `goedelsoup/bosc`, **Only select
repositories → bosc**.

## 3. Store the secrets and variables

Repo → **Settings → Secrets and variables → Actions**.

**Secrets:**

| Secret | Value |
| --- | --- |
| `RESEARCH_APP_ID` | the App ID from step 1 |
| `RESEARCH_APP_PRIVATE_KEY` | the full contents of the `.pem` private key |
| `ANTHROPIC_API_KEY` | a Claude API key (the run calls the model) |

**Variables:**

| Variable | Value | Meaning |
| --- | --- | --- |
| `RESEARCH_ENABLED` | `true` | **on / kill switch.** Anything other than `true` disables the workflow. |
| `RESEARCH_TOPIC` | *(optional)* | the topic the weekly cron investigates; empty = cron is a no-op |
| `RESEARCH_MAX_TURNS` | *(optional)* | agent turn cap (default 30; maps to `BOSC_RESEARCH_MAX_TURNS`) |
| `RESEARCH_MAX_PROPOSALS` | *(optional)* | issue proposals per run (default 5) |

## 4. Apply the branch-protection gates

The approval gates and runtime labels are managed as code in
[`.github/config`](../.github/config) (Pulumi). Apply them once with `pulumi up` (or by
setting the `PULUMI_STACK` variable so the `repo-config` workflow does it). This flips
`main` to require 1 approval + a CODEOWNERS review and creates the `agent-proposed`,
`needs-triage`, and `research-run` labels. See that directory's
[README](../.github/config/README.md).

## 5. Trigger a run

Once enabled, a run starts from any of:

- **Manual:** Actions → **research** → **Run workflow**, with a `topic` input.
- **Slash command:** comment `/research <topic>` on any issue or PR. Only a maintainer
  (`OWNER`/`MEMBER`/`COLLABORATOR`) can trigger it; other commenters are ignored.
- **Schedule:** the weekly cron uses `RESEARCH_TOPIC` (skipped if unset).

Each run opens a branch `research/run-<id>`, a PR labeled `research-run` whose body
carries the run's provenance + cost, and one issue per fresh proposal (labeled
`agent-proposed` + `needs-triage`, deduped against open issues). Review, then merge or
close.

## Turning it off

Set `RESEARCH_ENABLED` to anything but `true` (or delete it). In-flight runs finish;
no new run starts.
