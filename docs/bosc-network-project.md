# The BOSC Network project board

The **[BOSC Network](https://github.com/orgs/watermark-directory/projects/1)** org Project
is the single home for every watershed-point issue — the network's epics, per-site
`boom(...)` trackers, and the discipline tasks under them. It does **not** shard by site
(one board per site would fragment the `#323 → basin epic → boom → task` sub-issue tree
and kill the network-wide view). Instead one board carries four axes as fields, and every
question is a saved *view* over the same items.

## Scope

An issue belongs on the board when it carries `area:network` **or** any `site:*` label.
The existing native sub-issue tree (basin epic → `boom(basin): city` → tasks) is preserved
and shows inline via the built-in **Sub-issues progress** field.

The org Project's **auto-add-sub-issues** workflow additionally pulls the task children of
each `boom` tracker onto the board even when a child carries no `site:*` label of its own.
The sync therefore **inherits** Site/Basin/Readiness for such a child from its parent
tracker (Discipline is still computed from the child's own labels/title). Keep that
workflow enabled — it's how task issues reach the board.

## Fields (single-select)

| Field | Values | Set from |
|---|---|---|
| **Site** | the 34 registry slugs | the sole `site:<slug>` label (blank for multi-site epics) |
| **Basin** | Maumee · Great Miami · Little Miami · Scioto · Muskingum · Sandusky · Cuyahoga · Mahoning · Hocking | the basin the site(s) roll up to |
| **Discipline** | Hydrology · Grid · GIS/Footprint · Toxics · Sweep · Records/Evidence · Onboarding · Data-tier · Epic/umbrella | `area:*`/`needs:*` labels + title keywords |
| **Readiness** | registered · tracking · queued · building · live | **mirrors `data/sites.yaml` `status`** |

**Readiness is a mirror, never a source of truth.** `data/sites.yaml` (peer of
`watermark.sites` / `web/src/lib/sites.ts`) is canonical for a site's phase; the board
reflects it. To promote a site, edit `data/sites.yaml` — the daily sync re-mirrors the
field. The `readiness:*` labels exist so the same axis is queryable in plain issue search.

## Views (create in the UI — Project v2 view config is not in the API)

| View | Layout | Group by | Filter |
|---|---|---|---|
| **Readiness pipeline** | Board | Readiness | `label:type:epic label:area:network` (per-site `boom` trackers) |
| **By basin** | Board | Basin | — |
| **By site** | Table | Site | — (add the Sub-issues progress column) |
| **By discipline** | Board | Discipline | — |
| **Roadmap** | Roadmap | — | group/marker by Basin |
| **Ready for pickup** | Table | Site | `label:agent:available` sort by Priority |

Order the Readiness column left→right as the assembly line:
`registered → tracking → queued → building → live`.

## Keeping it current

- **`scripts/project_sync.py`** — adds in-scope issues and sets all four fields. Run
  `--issue N` for one, `--all` for a full resync, `--dry-run` to preview.
- **`.github/workflows/project-sync.yml`** — runs the script on issue events and on a daily
  cron (the readiness re-mirror). Needs an org secret **`PROJECT_TOKEN`** (a PAT with
  `project` + `repo`, or a fine-grained token with org Projects read/write + repo Issues
  read); the default `GITHUB_TOKEN` cannot write org Projects.

Discipline/basin inference is heuristic — a handful of issues may want a manual field nudge
on the board; that's expected and non-destructive.

`--all` **adds and re-fields** every board item but never **removes** one. That's deliberate:
the board intentionally retains items that carry no scope label of their own — the task
children auto-added from a `boom` tracker (they inherit their fields), and closed issues
(kept as history). Fields still regress correctly: when an item stops resolving to a value
(a site label removed, a discipline no longer matched) the sync clears that field rather
than leaving a stale one. Drop an item by removing it from the board in the UI.
