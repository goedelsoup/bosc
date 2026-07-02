"""Anthropic Admin usage + cost connector — the model-provider half of GreenOps (#1078).

Pulls the organization's **Admin** usage and cost reports —
``/v1/organizations/usage_report/messages`` and ``/v1/organizations/cost_report`` — through
the shared ``watermark.connectors.cached_get`` cache/offline/fixture machinery, and reduces
them to an :class:`AnthropicUsageReport`: token totals + USD cost over a trailing window,
attributed **by model** and **by workspace** so the by-task donut (#4/#1083) can hang off the
per-workspace/api-key split once per-task keys land.

**Auth.** The Admin key (``settings.anthropic_admin_key`` / ``ANTHROPIC_ADMIN_KEY``,
``sk-ant-admin01-…``) is distinct from the inference ``anthropic_api_key``. It is excluded
from the cache key (a secret must never vary the key or land in a committed fixture) and sent
only on the live request. Absent key + live path ⇒ :class:`AnthropicAdminError`; the caller
(the greenops assembly) degrades that source to a modeled assumption rather than crashing.

**Discipline.** Every figure is ``reference`` — an authoritative billing/usage export, not a
metered fact about our own consumption (:meth:`ProvenancedValue.from_reference`; ``verified``
is False). Nothing here is ``connector``-``verified``.

**A note on "inferences run".** The Messages Usage Report exposes token aggregates and
``web_search_requests`` only — there is **no per-request/message count** in the API. So this
connector reports the real token + cost totals (and the real web-search request count) and
does **not** synthesize a call count; the ``/about/sustainability`` "AI inferences run"
headline stays a modeled figure derived downstream (#4/#1083), never metered here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get
from watermark.greenops.model import GreenopsPeriod
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger

from . import GreenopsOfflineError

log = get_logger(__name__)

_ADMIN_BASE = "https://api.anthropic.com/v1/organizations"
_ANTHROPIC_VERSION = "2023-06-01"
# Cost amounts are decimal strings of the lowest currency unit — cents. "123.45" USD => $1.23.
_CENTS_PER_DOLLAR = 100.0


class AnthropicAdminError(RuntimeError):
    """The Admin API could not be queried live — most often a missing/invalid Admin key.

    Raised on the live path when ``settings.anthropic_admin_key`` is empty (a bare live pull
    would 401), so the caller degrades the Anthropic source to a modeled assumption with a
    clear reason rather than a cryptic HTTP error.
    """


class AnthropicUsageByModel(BaseModel):
    """Usage attributed to one model: token volume (usage report) + USD cost (cost report)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: str  # "claude-opus-4-8"
    input_tokens: int  # uncached + cache-creation + cache-read
    output_tokens: int
    cost: ProvenancedValue  # USD, reference


class AnthropicUsageByWorkspace(BaseModel):
    """Usage attributed to one workspace (the attribution the by-task split will hang off)."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None  # None => the organization's default workspace
    input_tokens: int
    output_tokens: int
    cost: ProvenancedValue  # USD, reference


class AnthropicUsageReport(BaseModel):
    """The reduced Anthropic Admin usage + cost report over a trailing window.

    Token totals and USD cost are ``reference`` (authoritative export). ``by_model`` and
    ``by_workspace`` carry the same figures split by their grouping dimension; ``by_model``
    is ranked by total token volume, descending. The greenops assembly (#1083) folds the
    headline totals into the ``GreenopsReport`` and uses the per-workspace split for the
    by-task donut once per-task keys land (#4).
    """

    model_config = ConfigDict(extra="forbid")

    period: GreenopsPeriod
    input_tokens: ProvenancedValue  # total input (uncached + cache create + cache read)
    output_tokens: ProvenancedValue
    cache_read_input_tokens: ProvenancedValue
    cache_creation_input_tokens: ProvenancedValue
    total_cost: ProvenancedValue  # USD across every cost type (tokens + server tools)
    web_search_requests: ProvenancedValue  # the one real request count the API exposes
    by_model: list[AnthropicUsageByModel]
    by_workspace: list[AnthropicUsageByWorkspace]
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values = [
            self.input_tokens,
            self.output_tokens,
            self.cache_read_input_tokens,
            self.cache_creation_input_tokens,
            self.total_cost,
            self.web_search_requests,
        ]
        values += [m.cost for m in self.by_model]
        values += [w.cost for w in self.by_workspace]
        return values


def _period_from_window(starting_at: str, ending_at: str) -> GreenopsPeriod:
    """Build the report window label from the RFC 3339 bounds (``ending_at`` is exclusive)."""
    start = datetime.fromisoformat(starting_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ending_at.replace("Z", "+00:00")) - timedelta(days=1)
    return GreenopsPeriod(
        label=f"{start:%b %Y}-{end:%b %Y}",
        start=f"{start:%Y-%m}",
        end=f"{end:%Y-%m}",
    )


def _fetch_report(report: str, key_params: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Fetch one Admin report, following pagination, reduced to ``{"data": [<buckets>]}``.

    The Admin key is deliberately absent from ``key_params`` (the cache key) and added only
    inside the live ``fetch``; the merged multi-page ``data`` is what lands in the cache/fixture.
    """
    # The live query mirrors key_params but spells `group_by` as the API's `group_by[]` array
    # and drops the connector-internal `report` marker (which is the path, not a query param).
    query: dict[str, Any] = {
        "starting_at": key_params["starting_at"],
        "ending_at": key_params["ending_at"],
        "bucket_width": key_params["bucket_width"],
        "group_by[]": key_params["group_by"],
    }

    def fetch() -> Any:
        if not settings.anthropic_admin_key:
            raise AnthropicAdminError(
                "no ANTHROPIC_ADMIN_KEY set; the Admin usage/cost report needs an Admin API "
                "key (sk-ant-admin01-…), distinct from the inference ANTHROPIC_API_KEY"
            )
        headers = {
            "x-api-key": settings.anthropic_admin_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            q = {**query, "page": page} if page else query
            resp = httpx.get(
                f"{_ADMIN_BASE}/{report}",
                params=q,
                headers=headers,
                timeout=settings.greenops_request_timeout_s,
            )
            resp.raise_for_status()
            body = resp.json()
            buckets.extend(body.get("data") or [])
            if not body.get("has_more"):
                break
            page = body.get("next_page")
            if not page:
                break
        return {"data": buckets}

    return cast(
        "dict[str, Any]",
        cached_get(
            "anthropic",
            key_params,
            fetch,
            cache_dir=settings.greenops_cache_dir,
            offline=settings.greenops_offline,
            fixtures_dir=settings.greenops_fixtures_dir,
            ttl_hours=settings.greenops_cache_ttl_hours,
            offline_error=GreenopsOfflineError,
        ),
    )


def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every result row across the report's time buckets."""
    rows: list[dict[str, Any]] = []
    for bucket in payload.get("data") or []:
        rows.extend(bucket.get("results") or [])
    return rows


def _int(value: Any) -> int:
    return int(value) if value is not None else 0


def build_usage_report(
    usage_payload: dict[str, Any],
    cost_payload: dict[str, Any],
    period: GreenopsPeriod,
) -> AnthropicUsageReport:
    """Reduce the raw usage + cost report payloads into an :class:`AnthropicUsageReport`.

    Pure over the two payloads (no I/O) so the offline fixtures exercise the real parsing,
    grouping, and USD conversion — not a pre-reduced blob.
    """
    usage_cite = f"Anthropic Admin usage_report/messages ({period.label})"
    cost_cite = f"Anthropic Admin cost_report ({period.label})"

    # --- usage report: token volume, by model and by workspace ---
    tot = {"uncached": 0, "cache_create": 0, "cache_read": 0, "output": 0, "web_search": 0}
    tok_by_model: dict[str, dict[str, int]] = {}
    tok_by_ws: dict[str | None, dict[str, int]] = {}
    for r in _results(usage_payload):
        cc = r.get("cache_creation") or {}
        cache_create = _int(cc.get("ephemeral_1h_input_tokens")) + _int(
            cc.get("ephemeral_5m_input_tokens")
        )
        uncached = _int(r.get("uncached_input_tokens"))
        cache_read = _int(r.get("cache_read_input_tokens"))
        output = _int(r.get("output_tokens"))
        input_total = uncached + cache_create + cache_read
        tot["uncached"] += uncached
        tot["cache_create"] += cache_create
        tot["cache_read"] += cache_read
        tot["output"] += output
        tot["web_search"] += _int((r.get("server_tool_use") or {}).get("web_search_requests"))
        model = r.get("model")
        if model is not None:
            slot = tok_by_model.setdefault(model, {"input": 0, "output": 0})
            slot["input"] += input_total
            slot["output"] += output
        ws = tok_by_ws.setdefault(r.get("workspace_id"), {"input": 0, "output": 0})
        ws["input"] += input_total
        ws["output"] += output

    # --- cost report: USD (from cents), by model (via description) and by workspace ---
    total_cents = 0.0
    cost_by_model: dict[str, float] = {}
    cost_by_ws: dict[str | None, float] = {}
    for r in _results(cost_payload):
        cents = float(r.get("amount") or 0)
        total_cents += cents
        model = r.get("model")  # None for non-token cost types (web search, code exec, …)
        if model is not None:
            cost_by_model[model] = cost_by_model.get(model, 0.0) + cents
        wsid = r.get("workspace_id")
        cost_by_ws[wsid] = cost_by_ws.get(wsid, 0.0) + cents

    def dollars(cents: float) -> float:
        return round(cents / _CENTS_PER_DOLLAR, 2)

    def ref(value: float, unit: str, cite: str) -> ProvenancedValue:
        return ProvenancedValue.from_reference(value, unit, cite, confidence="high")

    by_model = [
        AnthropicUsageByModel(
            model=model,
            input_tokens=toks["input"],
            output_tokens=toks["output"],
            cost=ref(dollars(cost_by_model.get(model, 0.0)), "USD", cost_cite),
        )
        for model, toks in sorted(
            tok_by_model.items(), key=lambda kv: kv[1]["input"] + kv[1]["output"], reverse=True
        )
    ]
    by_workspace = [
        AnthropicUsageByWorkspace(
            workspace_id=wsid,
            input_tokens=toks["input"],
            output_tokens=toks["output"],
            cost=ref(dollars(cost_by_ws.get(wsid, 0.0)), "USD", cost_cite),
        )
        for wsid, toks in sorted(
            tok_by_ws.items(), key=lambda kv: kv[1]["input"] + kv[1]["output"], reverse=True
        )
    ]

    return AnthropicUsageReport(
        period=period,
        input_tokens=ref(
            float(tot["uncached"] + tot["cache_create"] + tot["cache_read"]), "tokens", usage_cite
        ),
        output_tokens=ref(float(tot["output"]), "tokens", usage_cite),
        cache_read_input_tokens=ref(float(tot["cache_read"]), "tokens", usage_cite),
        cache_creation_input_tokens=ref(float(tot["cache_create"]), "tokens", usage_cite),
        total_cost=ref(dollars(total_cents), "USD", cost_cite),
        web_search_requests=ref(float(tot["web_search"]), "requests", usage_cite),
        by_model=by_model,
        by_workspace=by_workspace,
        note=(
            "Anthropic Admin usage_report/messages + cost_report over the window, attributed "
            "by model and by workspace. Figures are `reference` (a usage/billing export), not "
            "metered facts. The API exposes no per-message request count, so a literal "
            "'inferences run' figure is derived downstream (#4/#1083), never claimed here."
        ),
    )


def fetch_anthropic_usage(
    starting_at: str,
    ending_at: str,
    *,
    settings: Settings | None = None,
) -> AnthropicUsageReport:
    """Pull + reduce the Admin usage + cost reports over ``[starting_at, ending_at)`` (cached).

    ``starting_at`` / ``ending_at`` are RFC 3339 timestamps (``ending_at`` exclusive). The two
    reports are cached independently under connector ``anthropic``; an offline cache/fixture
    miss raises :class:`GreenopsOfflineError` naming the key to record.
    """
    settings = settings or get_settings()
    usage_key = {
        "report": "messages",
        "starting_at": starting_at,
        "ending_at": ending_at,
        "bucket_width": "1d",
        "group_by": ["model", "workspace_id"],
    }
    cost_key = {
        "report": "cost",
        "starting_at": starting_at,
        "ending_at": ending_at,
        "bucket_width": "1d",
        "group_by": ["workspace_id", "description"],
    }
    usage_payload = _fetch_report("usage_report/messages", usage_key, settings)
    cost_payload = _fetch_report("cost_report", cost_key, settings)
    return build_usage_report(
        usage_payload, cost_payload, _period_from_window(starting_at, ending_at)
    )


# --- committed reference artifact (data/reference/greenops/anthropic-usage.yaml) ------------

_REFERENCE_RELPATH = Path("reference") / "greenops" / "anthropic-usage.yaml"

_README = """\
# GreenOps — Anthropic Admin usage & cost

The model-provider slice of Watermark's own compute footprint (epic #1076, #1078): the
organization's Anthropic **Admin** usage and cost reports, reduced to token totals + USD cost
over a trailing window and attributed **by model** and **by workspace**.

Regenerate with `watermark greenops anthropic --write` (needs `ANTHROPIC_ADMIN_KEY`, an Admin
API key `sk-ant-admin01-…` distinct from the inference `ANTHROPIC_API_KEY`). Raw responses
cache under `data/cache/greenops/` (git-ignored); this committed YAML is regenerable.

## Source & discipline

- `anthropic-usage.yaml` — pulled from `/v1/organizations/usage_report/messages`
  (`group_by=model,workspace_id`) and `/v1/organizations/cost_report`
  (`group_by=workspace_id,description`), both at daily granularity, paginated.
- Every figure is `source: reference` — an authoritative usage/billing export, **not** a
  metered fact about our own consumption. Nothing here is `connector`-`verified`.
- **No inference count.** The Messages Usage Report exposes token aggregates and
  `web_search_requests` only — there is no per-request/message count. The `/about/sustainability`
  "AI inferences run" headline is therefore derived downstream (#4/#1083), never metered here.
"""


def write_anthropic_usage(
    report: AnthropicUsageReport, *, settings: Settings | None = None
) -> Path:
    """Persist the report as committed reference YAML + a README; return the YAML path."""
    settings = settings or get_settings()
    out = settings.data_dir / _REFERENCE_RELPATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (out.parent / "README.md").write_text(_README, encoding="utf-8")
    log.info("greenops.anthropic.wrote", path=str(out))
    return out


def load_anthropic_usage(path: Path) -> AnthropicUsageReport:
    """Load a committed :class:`AnthropicUsageReport` YAML."""
    return AnthropicUsageReport.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
