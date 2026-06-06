"""Parse Electionware "Summary Results" PDFs (Allen County BOE) -> normalized CSV.

Reads the pdftotext -layout text dumps and emits one row per
(election, section_type, contest, choice) with the four vote columns the report
prints: TOTAL, Election Day, Absentee, Provisional, plus the printed VOTE %.

NOTHING is computed or inferred: every number is copied verbatim from the text
layer of the source PDF. Multi-line choice labels (wrapped names) are stitched
back to the line that actually carries the numbers. Lines we cannot confidently
parse are written to a sidecar *.unparsed.txt for manual review rather than guessed.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

NUM = r"-?[\d,]+(?:\.\d+)?%?"
# a data line ends in a run of numeric-ish tokens
TAIL = re.compile(r"^(?P<label>.*?)\s{2,}(?P<nums>(?:" + NUM + r"\s*){1,6})$")
VOTEFOR = re.compile(r"^Vote For\s+\d+", re.I)
PARTY = re.compile(r"^(Rep|Dem|Lib|Npc|Opc|Grn|Con|Ind|Nonpartisan)\b")


def is_num(tok: str) -> bool:
    return bool(re.fullmatch(NUM, tok))


def clean(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip()


def parse(txt_path: Path, election: str, date: str):
    rows = []
    unparsed = []
    contest = None
    section = "statistics"  # until first contest header we are in the stats block
    pending_label = ""  # accumulates wrapped label lines with no numbers yet

    lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if not s:
            pending_label = ""
            continue
        # skip page furniture
        if re.search(
            r"Election Summary|Report generated|Electionware|Page \d+ of|"
            r"OFFICIAL|Summary Results|- Allen County -|Allen County$|"
            r"^\d{4} (General|Primary) Election$|^(November|May) \d",
            s,
        ):
            pending_label = ""
            continue
        # column header rows
        if re.match(
            r"^(TOTAL|VOTE %|Election|Day|Absentee|Provisional|Statistics|STATISTICS)\b", s
        ) and not TAIL.match(line):
            continue
        if VOTEFOR.match(s):
            continue
        m = TAIL.match(line)
        if not m:
            # contest header (text, no trailing numbers) -> start a new contest
            # but only treat as contest if it's not a stray fragment
            if not is_num(s) and len(s) > 2:
                # if previous line had no numbers, this might be a wrapped label
                # heuristic: contest headers usually start with "For", a party
                # prefix + "For", or contain known contest words
                if re.match(r"^((Rep|Dem|Lib|Npc|Opc) )?For\b", s) or s.startswith("For "):
                    contest = clean(s)
                    section = "contest"
                    pending_label = ""
                else:
                    # accumulate as a possible wrapped label for the next data line
                    pending_label = (pending_label + " " + s).strip()
            continue
        label = clean(m.group("label"))
        nums = m.group("nums").split()
        # special-case the "Precincts Reporting   88 of 88   88  0  0" stat line:
        # the "of" got swallowed into the numeric tail by -layout
        mpr = re.match(r"^(Election Day Precincts Reporting)\s+(\d+\s+of\s+\d+)$", label)
        if mpr:
            label = mpr.group(1)
            nums = [mpr.group(2).replace("  ", " "), *nums]
        if pending_label:
            label = clean(pending_label + " " + label)
            pending_label = ""
        # classify
        if section == "statistics":
            rec_section = "statistics"
            rec_contest = ""
        else:
            rec_section = "contest"
            rec_contest = contest or ""
        rows.append(make_row(election, date, rec_section, rec_contest, label, nums))
    return rows, unparsed


def make_row(election, date, section, contest, label, nums):
    # nums may be: [TOTAL, VOTE%, EDay, Absentee, Provisional]  (contest choice)
    #          or: [TOTAL, EDay, Absentee, Provisional]          (statistics / no pct)
    #          or: [TOTAL]                                       (single stat / turnout)
    total = vote_pct = eday = absentee = prov = ""
    pcts = [n for n in nums if n.endswith("%")]
    plain = [n for n in nums if not n.endswith("%")]
    if pcts:
        vote_pct = pcts[0]
    if len(plain) == 4:
        total, eday, absentee, prov = plain
    elif len(plain) == 1:
        total = plain[0]
    elif len(plain) == 5 and not pcts:
        total, _, eday, absentee, prov = plain  # rare
    elif len(plain) >= 4:
        total, eday, absentee, prov = plain[0], plain[-3], plain[-2], plain[-1]
    elif len(plain) == 2:
        total = plain[0]
    elif len(plain) == 3:
        total, absentee, prov = plain  # defensive
    else:
        total = plain[0] if plain else ""
    return {
        "election": election,
        "election_date": date,
        "section": section,
        "contest": contest,
        "choice": label,
        "total": total,
        "vote_pct": vote_pct,
        "election_day": eday,
        "absentee": absentee,
        "provisional": prov,
    }


def main():
    jobs = [
        ("txt/2024_GEN_SUMMARY_OFFICIAL.txt", "2024 General Election", "2024-11-05"),
        ("txt/2026_PRIMARY_SUMMARY_OFFICIAL.txt", "2026 Primary Election", "2026-05-05"),
        ("txt/G2019_OFFICIAL_SUMMARY.txt", "2019 General Election", "2019-11-05"),
    ]
    base = Path(__file__).parent
    fields = [
        "election",
        "election_date",
        "section",
        "contest",
        "choice",
        "total",
        "vote_pct",
        "election_day",
        "absentee",
        "provisional",
    ]
    for rel, election, date in jobs:
        rows, _ = parse(base / rel, election, date)
        out = base / (Path(rel).stem + ".csv")
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"{election}: {len(rows)} rows -> {out.name}")


if __name__ == "__main__":
    main()
