"""``watermark passages`` — regenerate the committed passage-excerpt artifact (#1589).

Extracts one page-cited passage per text-bearing page of every *published* source PDF into
``data/site/passages.ndjson`` — the LFS-independent index the ``search_passages`` MCP tool reads.
The source PDFs are Git-LFS-tracked and the frontend build checks out without LFS, so extraction
runs here (needs ``git lfs pull``) and the export reads the committed artifact rather than
re-extracting at build time. Regenerate whenever the publish allowlist or the source PDFs change.

**This command needs the tesseract binary too** (#1966). A page whose text layer is broken — a
source PDF whose ``ToUnicode`` CMap decodes to raw glyph indices — is re-read by OCR. Without
tesseract those pages degrade to ``pdf_text_damaged``, so a regen on a machine without it would
quietly turn 49 repaired rows back into damaged ones; the command says so rather than exiting
quietly.
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
    ocr = [p for p in passages if p.method == "ocr"]
    damaged = [p for p in passages if p.method == "pdf_text_damaged"]
    if ocr:
        console.print(f"  {len(ocr)} page(s) re-read by OCR (broken text layer, #1966)")
    if damaged and not ocr:
        console.print(
            f"[red]{len(damaged)} page(s) have a broken text layer and NONE was re-read — tesseract "
            "did not run (`brew install tesseract`). This artifact is a REGRESSION against the "
            "committed one; do not commit it.[/]"
        )
    elif damaged:
        console.print(
            f"  [yellow]{len(damaged)} page(s) could not be re-read (the page renders blank) — "
            "kept as a locator, marked `pdf_text_damaged`, not quotable:[/]"
        )
    for p in damaged[:5]:
        console.print(f"    {p.id}")
    if not passages:
        console.print(
            "[yellow]0 passages — the published PDFs are unresolved Git-LFS pointers; "
            "run `git lfs pull` and re-run.[/]"
        )
