"""``watermark passages`` — regenerate the committed passage-excerpt artifact (#1589).

Extracts one page-cited passage per text-bearing page of every *published* source PDF into
``data/site/passages.ndjson`` — the LFS-independent index the ``search_passages`` MCP tool reads.
The source PDFs are Git-LFS-tracked and the frontend build checks out without LFS, so extraction
runs here (needs ``git lfs pull``) and the export reads the committed artifact rather than
re-extracting at build time. Regenerate whenever the publish allowlist or the source PDFs change.
"""

from __future__ import annotations

from watermark.cli._base import app, console, get_settings


@app.command("passages")
def passages_cmd() -> None:
    """Extract published-PDF page passages → ``data/site/passages.ndjson`` (run ``git lfs pull`` first)."""
    from watermark.site.passages import extract_published_passages, write_committed_passages

    settings = get_settings()
    passages = extract_published_passages(settings)
    path = write_committed_passages(passages, settings)
    console.print(f"wrote {len(passages)} passages → {path.relative_to(settings.data_dir.parent)}")
    if not passages:
        console.print(
            "[yellow]0 passages — the published PDFs are unresolved Git-LFS pointers; "
            "run `git lfs pull` and re-run.[/]"
        )
