"""Stage 2 — extract.

Turn a :class:`SourceDocument` into a reviewed structured extraction. The
heavy lifting (visual reading of degraded scans, OCR correction) is delegated
to the Claude research agent; this module owns the *contract*: prompt assembly,
output location, and validation of the result against :mod:`bosc.models`.

The actual extraction logic is intentionally a seam — you will supply document
content and refine the prompt as real data arrives.
"""

from __future__ import annotations

from pathlib import Path

from bosc.agent.client import ResearchAgent
from bosc.config import Settings, get_settings
from bosc.logging import get_logger
from bosc.models import OPCSummary
from bosc.pipeline.ingest import SourceDocument

log = get_logger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are a meticulous document-extraction agent for Project BOSC. You read
public-records source documents (often degraded 300 DPI scans) and produce
faithful, structured YAML. Rules:
  * Read figures directly from the highest-resolution view available.
  * Mark any value you are not certain of with a leading ~ (approximate).
  * Never invent line items. Prefer omission over fabrication.
  * Record dollar totals/subtotals with high fidelity; flag uncertain digits.
  * Always note your basis, source page, and confidence.
"""


def output_path_for(doc: SourceDocument, kind: str, settings: Settings | None = None) -> Path:
    """Where the extraction for ``doc`` should be written."""
    settings = settings or get_settings()
    return settings.extracted_dir / f"{doc.path.stem}.{kind}.opc.yaml"


async def extract_document(
    doc: SourceDocument,
    instructions: str,
    *,
    agent: ResearchAgent | None = None,
    settings: Settings | None = None,
) -> str:
    """Run an agentic extraction over ``doc`` and return raw YAML text.

    ``instructions`` describes what to extract (which pages, what schema). The
    caller is responsible for persisting/validating the result; see
    :func:`extract_and_save`.
    """
    settings = settings or get_settings()
    agent = agent or ResearchAgent(
        model=settings.extract_model,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        settings=settings,
    )
    prompt = (
        f"Source document: {doc.path} (collection={doc.collection!r}, "
        f"{doc.size_bytes / 1e6:.1f} MB).\n\n{instructions}\n\n"
        "Return only the YAML extraction."
    )
    log.info("extract.start", doc_id=doc.doc_id, model=settings.extract_model)
    text = await agent.run(prompt)
    log.info("extract.done", doc_id=doc.doc_id, chars=len(text))
    return text


def validate_summary(path: str | Path) -> OPCSummary:
    """Load and validate a summary extraction, raising on schema violations."""
    summary = OPCSummary.from_yaml(path)
    log.info("extract.validated", path=str(path), sub_estimates=len(summary.sub_estimates))
    return summary
