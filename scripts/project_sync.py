#!/usr/bin/env python3
"""Keep the BOSC Network GitHub Project (org/watermark-directory/projects/1) in sync.

The board carries four single-select fields over every watershed-point issue:

  Site        — the sole ``site:<slug>`` label; inherited from the parent ``boom`` tracker
                when a sub-issue task carries no site label of its own
  Basin       — the major basin the site rolls up to
  Discipline  — inferred from the issue's own ``area:*``/``needs:*`` labels + title keywords
  Readiness   — the site's ``status`` in ``data/sites.yaml`` (canonical mirror; never hand-set)

Scope = any issue labelled ``area:network`` or ``site:*``. The org Project's
*auto-add-sub-issues* workflow also pulls the task children of each ``boom`` tracker onto
the board; those children often lack a site label, so their Site/Basin/Readiness are
inherited from the parent tracker here.

Readiness mirrors ``data/sites.yaml`` (peer of ``watermark.sites`` /
``web/src/lib/sites.ts``) — the registry is the single source of truth. To promote a site,
edit the registry; the daily sync re-mirrors the field. This script never writes back.

Usage:
  python scripts/project_sync.py --issue 512      # one issue (issue-event driven)
  python scripts/project_sync.py --all            # add scope issues + reprocess every item
  python scripts/project_sync.py --all --dry-run

Requires ``gh`` authenticated with a token carrying ``project`` + repo/org read scope
(in CI: a ``PROJECT_TOKEN`` secret — the default ``GITHUB_TOKEN`` cannot write org Projects).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from string import Template

import yaml

PROJECT_ID = "PVT_kwDOEamayM4BcU30"  # org/watermark-directory/projects/1 — "BOSC Network"
PROJECT_NUMBER = 1
OWNER = "watermark-directory"
REPO = "watermark-directory/the-watermark-directory"
SITES_YAML = pathlib.Path(__file__).resolve().parent.parent / "data" / "sites.yaml"

# Major-basin roll-up. Small and stable; basin_label in sites.yaml is a display string,
# so the grouping lives here rather than being parsed out of it.
BASIN = {
    "Maumee": [
        "lima",
        "fort-wayne",
        "defiance",
        "findlay",
        "toledo",
        "van-wert",
        "bryan",
        "ottawa",
    ],
    "Great Miami": [
        "urbana",
        "springfield",
        "wpafb",
        "hamilton-middletown",
        "troy-piqua",
        "sidney",
        "greenville",
    ],
    "Little Miami": ["xenia", "wilmington"],
    "Scioto": ["new-albany", "columbus", "piketon"],
    "Muskingum": ["coshocton", "newark", "zanesville"],
    "Sandusky": ["sandusky", "fremont", "tiffin", "bucyrus"],
    "Cuyahoga": ["cleveland", "akron"],
    "Mahoning": ["lordstown", "youngstown"],
    "Hocking": ["lancaster", "athens", "logan"],
}
SLUG2BASIN = {s: b for b, ss in BASIN.items() for s in ss}


def sh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command as an argument list (no shell), capturing text output."""
    return subprocess.run(args, capture_output=True, text=True)


def gql(query: str) -> dict:
    r = sh(["gh", "api", "graphql", "-f", f"query={query}"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout)


def load_status() -> dict[str, str]:
    """slug -> status ('live'|'building'|'queued'|'tracking') from data/sites.yaml.

    Structured parse of the canonical registry (top level: ``{sites: [...]}``) — robust to
    quoting, ordering, and comments in a way the previous regex scan was not.
    """
    data = yaml.safe_load(SITES_YAML.read_text())
    return {s["slug"]: s["status"] for s in data["sites"] if "slug" in s and "status" in s}


_Q_FIELDS = Template(
    '{node(id:"$pid"){... on ProjectV2{fields(first:30){nodes{... on '
    "ProjectV2SingleSelectField{id name options{id name}}}}}}}"
)


def field_map() -> dict[str, dict]:
    data = gql(_Q_FIELDS.substitute(pid=PROJECT_ID))
    nodes = data["data"]["node"]["fields"]["nodes"]
    return {
        f["name"]: {"id": f["id"], "opts": {o["name"]: o["id"] for o in f["options"]}}
        for f in nodes
        if f.get("name") in ("Site", "Basin", "Discipline", "Readiness")
    }


def discipline(title: str, labels: set[str]) -> str | None:
    t = title.lower()
    if "type:epic" in labels:
        return "Epic/umbrella"
    if "sweep" in t:
        return "Sweep"
    if "area:hydrology" in labels or any(
        k in t for k in ("7q10", "hydrology", "receiving water", "low-flow", "aquifer", "wwtp")
    ):
        return "Hydrology"
    if "area:grid" in labels or any(k in t for k in ("eia-861", "pjm", "utility")):
        return "Grid"
    if "rsei" in t or "toxic" in t:
        return "Toxics"
    if (
        "needs:gis" in labels
        or "needs:site-target" in labels
        or any(k in t for k in ("parcel", "footprint", "geometry"))
    ):
        return "GIS/Footprint"
    if (
        "area:evidence" in labels
        or "needs:permit" in labels
        or any(k in t for k in ("records request", "primary record", "npdes"))
    ):
        return "Records/Evidence"
    if "onboard" in t:
        return "Onboarding"
    if "area:data-tier" in labels or "area:frontend" in labels:
        return "Data-tier"
    return None


def _sole_site(labels: set[str]) -> str | None:
    sites = sorted(lb.split(":", 1)[1] for lb in labels if lb.startswith("site:"))
    return sites[0] if len(sites) == 1 else None


_Q_RESOLVE = Template(
    '{repository(owner:"$owner",name:"the-watermark-directory"){issue(number:$num){'
    "title labels(first:30){nodes{name}} "
    "parent{labels(first:30){nodes{name}}}}}}"
)


def resolve(number: int, status: dict[str, str]) -> dict[str, str | None]:
    """Return the four field values for one issue (with parent-inheritance for Site)."""
    iss = gql(_Q_RESOLVE.substitute(owner=OWNER, num=number))["data"]["repository"]["issue"]
    if iss is None:
        return {"Site": None, "Basin": None, "Discipline": None, "Readiness": None}
    labels = {n["name"] for n in iss["labels"]["nodes"]}
    site = _sole_site(labels)
    if site is None and iss.get("parent"):
        site = _sole_site({n["name"] for n in iss["parent"]["labels"]["nodes"]})
    basin = SLUG2BASIN.get(site) if site else None
    return {
        "Site": site,
        "Basin": basin,
        "Discipline": discipline(iss["title"], labels),
        "Readiness": status.get(site) if site else None,
    }


_SCOPE_LIMIT = 1000  # gh search issues hard cap


def scope_numbers() -> list[int]:
    """All open issues labelled area:network or site:* — one robust comma-OR search."""
    labels = ",".join(["area:network"] + [f"site:{s}" for s in SLUG2BASIN])
    r = sh(
        ["gh", "search", "issues", "--repo", REPO, "--state", "open",
         f"label:{labels}", "--limit", str(_SCOPE_LIMIT), "--json", "number"]
    )  # fmt: skip
    nums = [it["number"] for it in json.loads(r.stdout or "[]")]
    if len(nums) >= _SCOPE_LIMIT:
        print(
            f"  ! scope search returned the {_SCOPE_LIMIT}-result cap — some in-scope issues "
            "may be missing; add pagination if the network has grown this large.",
            file=sys.stderr,
        )
    return nums


_Q_ITEMS = Template(
    '{node(id:"$pid"){... on ProjectV2{items(first:100$after){pageInfo{hasNextPage '
    "endCursor} nodes{id content{... on Issue{number}}}}}}}"
)


def project_items() -> list[dict]:
    """[{item_id, number}] for every issue currently on the board (paginated)."""
    items, cursor = [], None
    while True:
        after = f',after:"{cursor}"' if cursor else ""
        data = gql(_Q_ITEMS.substitute(pid=PROJECT_ID, after=after))
        page = data["data"]["node"]["items"]
        for n in page["nodes"]:
            c = n.get("content") or {}
            if c.get("number"):
                items.append({"item_id": n["id"], "number": c["number"]})
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


_Q_ISSUE_ID = Template(
    '{repository(owner:"$owner",name:"the-watermark-directory"){issue(number:$num){id}}}'
)
_M_ADD = Template(
    'mutation{addProjectV2ItemById(input:{projectId:"$pid",contentId:"$cid"}){item{id}}}'
)
_M_SET = Template(
    'mutation{updateProjectV2ItemFieldValue(input:{projectId:"$pid",itemId:"$iid",'
    'fieldId:"$fid",value:{singleSelectOptionId:"$oid"}}){projectV2Item{id}}}'
)
_M_CLEAR = Template(
    'mutation{clearProjectV2ItemFieldValue(input:{projectId:"$pid",itemId:"$iid",'
    'fieldId:"$fid"}){projectV2Item{id}}}'
)


def add_item(number: int) -> str:
    cid = gql(_Q_ISSUE_ID.substitute(owner=OWNER, num=number))["data"]["repository"]["issue"]["id"]
    return gql(_M_ADD.substitute(pid=PROJECT_ID, cid=cid))["data"]["addProjectV2ItemById"]["item"][
        "id"
    ]


def set_field(item_id: str, fields: dict, name: str, opt: str | None) -> None:
    fid = fields[name]["id"]
    if opt is None:
        # Regress the field to empty — otherwise a value that no longer resolves (e.g. a site
        # label removed, or a discipline no longer matched) would stay stuck on the item.
        gql(_M_CLEAR.substitute(pid=PROJECT_ID, iid=item_id, fid=fid))
        return
    oid = fields[name]["opts"].get(opt)
    if not oid:
        print(f"  ! unknown option {opt!r} in field {name}")
        return
    gql(_M_SET.substitute(pid=PROJECT_ID, iid=item_id, fid=fid, oid=oid))


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--issue", type=int)
    g.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    status = load_status()

    if args.issue:
        targets = [{"item_id": None, "number": args.issue}]
    else:
        on_board = {i["number"]: i for i in project_items()}
        for n in scope_numbers():  # add any newly-labelled scope issue not yet present
            on_board.setdefault(n, {"item_id": None, "number": n})
        targets = list(on_board.values())

    print(f"{len(targets)} target(s) (dry={args.dry_run})")
    fields = None if args.dry_run else field_map()

    for t in sorted(targets, key=lambda x: x["number"]):
        vals = resolve(t["number"], status)
        print(f"#{t['number']:<5} " + " ".join(f"{k}={v or '-'}" for k, v in vals.items()))
        if args.dry_run:
            continue
        item_id = t["item_id"] or add_item(t["number"])
        for name in ("Site", "Basin", "Discipline", "Readiness"):
            set_field(item_id, fields, name, vals[name])
    return 0


if __name__ == "__main__":
    sys.exit(main())
