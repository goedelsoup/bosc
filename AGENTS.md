# AGENTS.md

Orientation for automated agents working in this repo. For project architecture,
read [CLAUDE.md](CLAUDE.md). This file is the execution contract — the conventions
and sharp edges for agentic runs (research and task-execution alike).

## Start here — route by task

| If your task is… | Read |
|---|---|
| Start a branch/worktree for an issue | [Branch & worktree](#branch--worktree) below |
| Run the research agent | [Research tasks](#research-tasks) below, then [README.md](README.md) |
| Extract a document / add an extraction | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Onboard a new watershed-point site | [docs/onboarding.md](docs/onboarding.md) |
| Frontend / Astro (`web/`) | [web/README.md](web/README.md) |
| Task reference, CI gate, module map | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Data conventions & chain of custody | [CONTRIBUTING.md](CONTRIBUTING.md) |

When in doubt, the flow is: pick a worktree → make the change → `mise run check`
→ write the PR body → exit. Each step is a section below.

## Branch & worktree

Never work directly on `main`. Each task gets its own **sibling worktree** created
through the `wt:*` mise tasks — they encode the issue→branch naming and the
sibling-path layout, so prefer them over raw `git worktree`/`git checkout`.

```bash
mise run wt:new 123          # branch from issue #123 → ../123-short-title/
mise run wt:new my-feature   # plain branch name, no issue
cd "$(mise run wt:path 123)" # jump into the worktree
```

`wt:new` prints the worktree path on stdout. It branches from `main` by default
(`--base <ref>` to override), reuses an existing `<issue>-*` branch instead of
spawning a second one, and tracks `origin/<branch>` if the branch already exists
remotely. Worktrees live as siblings of `main` inside the `watermark-directory/`
parent, named `<issue-number>-<slug>` so they round-trip by issue number.

When the task is done and merged, clean up:

```bash
mise run wt:list                  # show all worktrees
mise run wt:rm 123 --delete-branch # remove worktree + local branch
```

## Gate before declaring done

```bash
mise run check
```

This runs ruff lint + format check + mypy strict + pytest. A change is not done
until `check` is green. For changes that touch `web/`, also run
`mise run //web:check`.

## Checkout

Always use `lfs: false` when checking out this repo. `data/documents/` contains
~5.4 GB of Git LFS source documents — smudging them fills the disk and is
unnecessary for almost all automated work.

## Environment

```bash
uv sync --extra dev    # install all deps including dev extras
uv run bosc ...        # all CLI commands go through uv run
```

Python 3.11. Settings are read via `watermark.config.get_settings()` — never read
`os.environ` directly. All settings are `WATERMARK_`-prefixed.

## Data discipline (important)

- `data/documents/**` is **immutable evidence** — never modify, rename, or delete
  any file here. The research workflow has a hard chain-of-custody check that aborts
  if any source byte is touched.
- `data/extracted/**` is the reviewed artifact. Changes require a cited source.
- `data/reference/**` is committed authoritative external data. Changes must be
  regenerable from a documented connector.
- `data/research/**` is the output directory for `bosc research run` — commit the
  whole directory as produced.

## Research tasks

Research runs write to `data/research/<slug>/`. Commit the output directory:

```bash
git add data/research/
git commit -m "research: <topic>"
```

The `findings.md` and `manifest.yaml` inside are the reviewable artifacts.

## Custom PR description

The Orlop agent harness sets `$AGENT_PR_BODY_FILE` to a temp file path. Write a
markdown PR body there before the process exits and the harness will use it as the
PR description. If the file is absent or empty, the harness generates a default body
from the issue title and body.

## Issue & PR labels

The label vocabulary is **managed as code** in
[`.github/config/`](.github/config/README.md) (`index.ts`, applied by Pulumi); run
`gh label list` for the live set. The namespaces an agent interacts with:

- **`agent:*`** — the work queue. `agent:available` = staged for pickup (claim per the
  Orlop queue protocol: assign yourself + swap to `agent:claimed`); `agent:claimed` =
  in flight; `agent:needs-human` = blocked (see below).
- **`orlop:*`** — board-managed by the [Orlop](https://github.com/tonnetz-io/orlop) HITL
  board; **agents don't set these**. `orlop:hold` means *do not pick up or merge*.
- **`status:*`** — triage state on proposed work: `status:agent-proposed` (opened by a
  research run), `status:needs-triage` (inert until a maintainer reviews), `status:blocked`.
- **`type:*` / `area:*` / `lead:*`** — the categorization a PR/issue carries (kind, subsystem,
  open-leads board). See [CONTRIBUTING.md](CONTRIBUTING.md) for the PR-labeling convention.

## Stuck / blocked

Exit with a non-zero status code. The harness catches it, adds `agent:needs-human`
to the issue, and stops — a human will review and unblock. Never silently swallow
errors that prevent the task from being completed correctly.

## Site axis

The network hosts multiple watershed-point sites. Per-site values live on
`SiteProfile` in `watermark.sites` — never hard-code a Lima/Allen-County value.
Select a site with `--site <slug>` or `WATERMARK_SITE=<slug>`. The default site
is `lima`.
