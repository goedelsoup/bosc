"""Build the ``open-questions`` feed (#1568) — the corpus's still-open threads, aggregated.

BOSC asks one question across a network of watershed-point sites, and holds the *unanswered*
parts of it as first-class data. This feed gathers them into one flat, provenanced list so the
frontend (and the research agent) can read "what's still open here" without walking three stores.

Like :mod:`watermark.site.facts` and :mod:`watermark.site.catalog_index`, it is a **post-pass
projection** — it re-loads no corpus, mints no claims, and copies no payloads it didn't already
ship. It reads two already-assembled feeds:

* ``leads`` — the per-site open board (`watermark.site.leads`, wired to the GitHub
  ``lead:kind:*`` / ``lead:status:*`` label vocabulary). Every ``[open]``-tagged lead is an open
  question; an ``[inference]``-tagged lead is a *labeled reading*, not a gap, so it is excluded.
* ``hypothesis-assessments`` — the ``(site x hypothesis)`` evidence matrix
  (`watermark.hypotheses`). Every ``[open]``-tagged cell is a documented gap: no nexus yet for this
  site under that boom-origin lens. The ``hypotheses`` feed supplies each lens's human label.

This ports yidam's ``open-questions`` model faithfully: a node is open when it carries the
``[open]`` tag (``claim_tag == "open"``), the exact rule
:func:`watermark.site.corpus_mirror.render_open_questions` replicates. The two sources already
carry that tag structurally (a lead's ``tag``; a cell's ``tag``), so the projection is a filter,
not a re-derivation.

Skipped (the feed is dropped, ``hasFeed("open-questions")`` false) for a site with no open
threads, so the frontend degrades rather than shipping an empty list — the same convention as
``leads``/``facts``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from watermark.logging import get_logger
from watermark.site.feeds import OpenQuestionItem

log = get_logger(__name__)


def _oneline(text: str) -> str:
    """Collapse a multi-line ``detail`` block to a single line (mirrors corpus_mirror._oneline)."""
    return " ".join(str(text).split())


def _project_leads(rows: Sequence[Mapping[str, Any]]) -> list[OpenQuestionItem]:
    """Every ``[open]``-tagged lead → an open question (``[inference]`` leads excluded)."""
    items: list[OpenQuestionItem] = []
    for row in rows:
        if row.get("tag") != "open":
            continue  # a labeled reading, not an open gap — excluded, like render_open_questions
        items.append(
            OpenQuestionItem(
                id=str(row.get("id") or ""),
                origin="lead",
                question=str(row.get("title") or ""),
                detail=_oneline(str(row.get("detail") or "")),
                source=str(row.get("source") or ""),
                kind=row.get("kind"),
                status=row.get("status"),
                issue=row.get("issue"),
            )
        )
    return items


def _project_hypothesis_cells(
    rows: Sequence[Mapping[str, Any]],
    lens_labels: Mapping[str, str],
) -> list[OpenQuestionItem]:
    """Every ``[open]``-tagged matrix cell → an open thread under its boom-origin lens.

    Provenance is the cell's committed matrix file (`data/hypotheses/<hid>/<site>.yaml`) — an
    open cell carries no ``Citation`` by rule (only an ``open`` cell may have none), so its
    ``source`` is *where the gap is recorded*, not a fabricated citation.
    """
    items: list[OpenQuestionItem] = []
    for cell in rows:
        if cell.get("tag") != "open":
            continue
        hid = str(cell.get("hypothesis") or "")
        site = str(cell.get("site") or "")
        label = lens_labels.get(hid, hid)
        fields = cell.get("fields") or {}
        detail = f"No documented nexus yet for {site} under {label}."
        if fields:
            detail += " Fields: " + ", ".join(f"{k}={v}" for k, v in fields.items()) + "."
        items.append(
            OpenQuestionItem(
                id=f"hyp:{hid}:{site}",
                origin="hypothesis",
                question=f"Open thread — {label} @ {site}",
                detail=detail,
                source=f"data/hypotheses/{hid}/{site}.yaml",
                hypothesis=hid,
                hypothesis_label=label,
                signal=cell.get("signal"),
            )
        )
    return items


def _lens_labels(hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Map a hypothesis id → its human lens label ("H1 Water & Coercion") from the feed rows."""
    labels: dict[str, str] = {}
    for hyp in hypotheses:
        hid = str(hyp.get("id") or "")
        if not hid:
            continue
        number = str(hyp.get("number") or "").strip()
        name = str(hyp.get("name") or "").strip()
        labels[hid] = f"{number} {name}".strip() or hid
    return labels


def build_open_questions(payloads_by_feed: Mapping[str, Any]) -> list[OpenQuestionItem]:
    """Project the assembled ``leads`` + ``hypothesis-assessments`` feeds into open questions.

    ``payloads_by_feed`` maps a feed name to its parsed payload (a list of row dicts for a
    collection feed) — the just-assembled feeds, so no corpus re-load. Leads come first (the
    concrete, sourced board), then the hypothesis-matrix threads (ordered by the ``hypotheses``
    feed's lens order); the result is a stable, deduped-by-``id`` list.
    """
    leads = payloads_by_feed.get("leads")
    cells = payloads_by_feed.get("hypothesis-assessments")
    hypotheses = payloads_by_feed.get("hypotheses")

    collected: list[OpenQuestionItem] = []
    if isinstance(leads, Sequence):
        collected.extend(_project_leads(leads))
    if isinstance(cells, Sequence):
        lens_labels = _lens_labels(hypotheses if isinstance(hypotheses, Sequence) else [])
        collected.extend(_project_hypothesis_cells(cells, lens_labels))

    # Dedup on the stable id (a lead id can't collide with a `hyp:` id; belt-and-suspenders).
    questions: list[OpenQuestionItem] = []
    seen: set[str] = set()
    for q in collected:
        if q.id in seen:
            continue
        seen.add(q.id)
        questions.append(q)

    log.info(
        "open_questions.projected",
        total=len(questions),
        leads=sum(1 for q in questions if q.origin == "lead"),
        hypotheses=sum(1 for q in questions if q.origin == "hypothesis"),
    )
    return questions
