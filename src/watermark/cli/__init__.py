"""``watermark`` command-line interface.

Commands:
    watermark version
    watermark ingest                 # inventory source documents
    watermark reconcile <file>       # arithmetic checks over a summary extraction
    watermark ask "<question>"       # ask the research agent
    watermark extract <doc-id> ...   # run an agentic extraction (seam for your data)
    watermark export                 # write the typed content bundle the frontend reads
    watermark corpus-mirror          # project the corpus into yidam node format (.yidam/corpus/)
    watermark wiki-lint              # audit the wiki [[link]] cross-reference graph (corpus-hygiene)
"""

from __future__ import annotations

# Import the command submodules so their @app.command / @<sub>_app.command
# decorators run and register on the shared app + sub-apps in _base.
from watermark.cli import (  # noqa: F401
    air,
    catalog,
    corpus_mirror,
    facility,
    gis,
    greenops,
    grid,
    hydrology,
    hypotheses,
    imagery,
    leads,
    objectstore,
    oepa,
    passages,
    pipeline,
    poi,
    reference,
    research,
    retrieval,
    sites,
    subdivisions,
    sweep,
    wiki,
)
from watermark.cli._base import app

__all__ = ["app"]


if __name__ == "__main__":
    app()
