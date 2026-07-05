"""Pipeline task taxonomy for per-task Anthropic usage attribution (#1080).

Every pipeline stage that calls a Claude model is a *task*. Routing each task through a
distinct Anthropic API key — one bound to its own Anthropic **workspace** — makes the Admin
usage report (:mod:`watermark.greenops.connectors.anthropic`, #1078) attribute calls by
workspace. That per-workspace split is what upgrades the GreenOps "AI · by task type" donut
(#1083) from a modeled ``assumption`` to a ``connector`` figure.

The key *selection* lives on :class:`watermark.config.Settings` (``anthropic_key_for``); this
module is the single source of truth for the task list plus the donut labels, so the config
resolver, the agent wrappers, and the downstream footprint builder share one vocabulary
instead of scattering string literals. A task's env-var key is
``WATERMARK_ANTHROPIC_KEY_<TASK>`` (see :class:`~watermark.config.Settings`).
"""

from __future__ import annotations

from enum import StrEnum


class PipelineTask(StrEnum):
    """A model-calling pipeline stage — the unit of Anthropic usage attribution.

    The value doubles as the config-field suffix (``anthropic_key_<value>``) and the env-var
    suffix (``WATERMARK_ANTHROPIC_KEY_<VALUE>``), so it must stay a bare identifier.
    """

    EXTRACT = "extract"  # structured vision/text extraction (watermark.agent.extractor)
    CORROBORATE = "corroborate"  # the self-correcting reconcile/repair loop (#40, not yet live)
    ASK = "ask"  # Search & Ask + free-form research (watermark.agent.client)
    DRAFT = "draft"  # distilling findings into drafted prose/proposals

    @classmethod
    def coerce(cls, value: PipelineTask | str | None, *, default: PipelineTask) -> PipelineTask:
        """Best-effort convert ``value`` to a task, falling back to ``default``.

        Mirrors the tolerant lookup in :meth:`watermark.config.Settings.anthropic_key_for`:
        an unknown string (or ``None``) never raises — it resolves to ``default``. Normalizing
        a caller-supplied ``PipelineTask | str`` once, up front, keeps later ``.value`` access
        safe (e.g. a trace attribute set mid-turn) instead of risking a ``ValueError`` there.
        """
        if value is None:
            return default
        try:
            return cls(value)
        except ValueError:
            return default

    @property
    def label(self) -> str:
        """The human label this task carries on the /about/sustainability by-task donut."""
        return _DONUT_LABELS[self]


# Donut panel labels (watermark.greenops.footprint AiByTask). Kept here so #1083 maps the
# Admin report's per-workspace split back to a task label from one place.
_DONUT_LABELS: dict[PipelineTask, str] = {
    PipelineTask.EXTRACT: "Structured extraction",
    PipelineTask.ASK: "Search & Ask",
    PipelineTask.CORROBORATE: "Corroboration assist",
    PipelineTask.DRAFT: "Drafting summaries",
}
