# `.github/config` — repository configuration as code (Pulumi)

This Pulumi project manages the GitHub configuration of the **`bosc`** repository
declaratively: repository settings, branch protection for `main`, and the research
App's runtime labels. Change the config by editing [`index.ts`](index.ts) and
running `pulumi up` (locally or via the [`repo-config`
workflow](../workflows/repo-config.yml)) — not by clicking around in the GitHub UI.

## What it manages

- **Repository settings** (`github.Repository` `"bosc"`) — description,
  visibility, features (issues / projects / wiki), and the merge-button policy.
  The resource is `protect`ed and `retainOnDelete`, so Pulumi will **never delete
  the repo**, even on `pulumi destroy` or if the resource is removed from the
  program.
- **Branch protection** (`github.BranchProtection` `"main"`) — requires the
  `check` CI job to pass, optionally requires the branch be up to date, blocks
  force-pushes and deletions, requires conversation resolution, and routes all
  changes through a pull request. Required approvals, **code-owner reviews**, and
  admin-enforcement are tunable via stack config (defaults: 1 approval + a
  CODEOWNERS review, admins not enforced).
- **Runtime labels** (`github.IssueLabel`) — `agent-proposed`, `needs-triage`,
  `research-run`, `submission`: the vocabulary the automation tags its proposed
  issues/PRs with, so the work is inert until a human triages it. `agent-proposed` +
  `research-run` are the [research GitHub App](../../data/research/) (Epic
  [#57](https://github.com/watermark-directory/the-watermark-directory/issues/57)); `submission` is the public
  [submissions form](../../docs/submissions-api.md) (Epic
  [#56](https://github.com/watermark-directory/the-watermark-directory/issues/56)); both share `needs-triage`.
  Pulumi manages only these four; pre-existing repo labels are left alone.

## Approval gates & the research App (Epic 5.4)

`main` requires **one approving review and a [CODEOWNERS](../CODEOWNERS) review**
(`* @goedelsoup`). The research App opens PRs and proposed issues under its own
identity but is **not a code owner and not a repo admin**, so it cannot approve or
merge its own PR — a human (`@goedelsoup`) must review first. `enforceAdmins` stays
`false` so the solo human maintainer (a repo admin and a code owner) can still merge
their own work via admin override — GitHub forbids approving one's *own* PR, and
that override is the escape hatch. Flip `enforceAdmins` to `true` only once there's
a second reviewer.

## Stack config (`Pulumi.prod.yaml`, committed — no secrets)

| Key | Default | Meaning |
| --- | --- | --- |
| `github:owner` | `goedelsoup` | GitHub owner / org |
| `repo` | `bosc` | repository name |
| `requiredApprovals` | `1` | approving reviews required on `main` |
| `requireCodeOwnerReviews` | `true` | also require a CODEOWNERS review |
| `enforceAdmins` | `false` | also apply protection to admins |
| `requireUpToDate` | `true` | branch must be current before merge |

The GitHub **token** is never committed. Supply it via the `GITHUB_TOKEN`
environment variable — a PAT or GitHub App token with **Administration: write**
on the repo. (The default Actions `GITHUB_TOKEN` is *not* sufficient for branch
protection or repo settings.)

## Prerequisites

- Node.js LTS (managed by mise) — run `npm install` in this directory.
- The Pulumi CLI and a state backend: Pulumi Cloud (`PULUMI_ACCESS_TOKEN`) or a
  local file backend (`pulumi login --local`).

## Bootstrap (one-time)

The repository already exists, so adopt it into Pulumi state before the first
apply — otherwise Pulumi tries to *create* a repo named `bosc` and fails:

```bash
cd .github/config
npm install
pulumi stack init prod            # or: pulumi stack select prod
export GITHUB_TOKEN=...           # admin-scoped PAT / App token
pulumi import github:index/repository:Repository watermark bosc
pulumi preview                    # review: should show only the new BranchProtection
pulumi up
```

## Everyday use

```bash
cd .github/config
# edit index.ts ...
pulumi preview     # see the diff
pulumi up          # apply
```

## CI

[`../workflows/repo-config.yml`](../workflows/repo-config.yml) runs `pulumi
preview` on pull requests that touch this directory (commenting the plan on the
PR) and `pulumi up` when those changes land on `main`. It needs:

- **`PULUMI_ACCESS_TOKEN`** (secret) — Pulumi Cloud token for state.
- **`GH_ADMIN_TOKEN`** (secret) — PAT / App token with **Administration: write**
  (the provider token; the default `GITHUB_TOKEN` can't manage protection).
- **`PULUMI_STACK`** (Actions *variable*) — fully-qualified stack name, e.g.
  `your-pulumi-org/bosc-repo-config/prod`.

`PULUMI_STACK` doubles as the on-switch: the job is gated on it, so until it's
set the workflow is **skipped** (not failed) on PRs that touch this directory.
Set the variable and the two secrets together to activate it.
