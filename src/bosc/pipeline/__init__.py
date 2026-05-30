"""The BOSC research pipeline: ingest -> extract -> analyze.

Each stage is a small, independently testable module:

* :mod:`bosc.pipeline.ingest`  — discover and register source documents.
* :mod:`bosc.pipeline.extract` — turn a document into structured data.
* :mod:`bosc.pipeline.analyze` — reconcile and reason over structured data.
"""

from __future__ import annotations

from bosc.pipeline import analyze, extract, ingest

__all__ = ["analyze", "extract", "ingest"]
