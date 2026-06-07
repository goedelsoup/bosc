"""Smoke test for the static HTML renderer (`bosc.site.render`)."""

from __future__ import annotations

from pathlib import Path

from bosc.config import Settings
from bosc.site.build import build_site
from bosc.site.render import _rewrite_target, render_site

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_link_rewriting() -> None:
    # Internal markdown links gain .html; the landing page maps to the root index.
    assert _rewrite_target("entities.md") == "entities.html"
    assert _rewrite_target("docs/DOSSIER.md") == "docs/DOSSIER.html"
    assert _rewrite_target("../oepa/README.md") == "../oepa/README.html"
    assert _rewrite_target("home.md") == "index.html"
    assert _rewrite_target("entities.md#graph") == "entities.html#graph"
    # External / non-markdown / anchor links are untouched.
    assert _rewrite_target("https://example.org/x.md") == "https://example.org/x.md"
    assert _rewrite_target("mailto:a@b.com") == "mailto:a@b.com"
    assert _rewrite_target("#section") == "#section"
    assert _rewrite_target("../../documents/aedg/PRR-01-bundle.ocr.pdf").endswith(".pdf")


def test_render_site_emits_html(tmp_path: Path) -> None:
    settings = Settings(data_dir=REPO_ROOT / "data")
    web = tmp_path / "web"
    site = tmp_path / "site"

    build_site(settings, web_dir=web)
    result = render_site(web, site)

    assert result.pages > 0
    # The landing page renders to the root index.html (no custommill home.html hack).
    index = site / "index.html"
    assert index.is_file()
    index_html = index.read_text(encoding="utf-8")
    assert '<nav class="sidebar"' in index_html
    assert "Project BOSC" in index_html

    # A mirrored deep page renders at its 1:1 path with a path-to-root asset prefix.
    deep = site / "data" / "extracted" / "aedg" / "README.html"
    assert deep.is_file()
    assert "../../../assets/site.css" in deep.read_text(encoding="utf-8")

    # The entity graph page carries a Mermaid block for client-side rendering.
    entities = (site / "entities.html").read_text(encoding="utf-8")
    assert "mermaid" in entities

    # The landing-page admonition becomes a styled callout, and its .md links became .html.
    assert "admonition" in index_html
    assert "entities.html" in index_html and "entities.md" not in index_html

    # Static assets were copied through verbatim.
    assert (site / "assets" / "extra.css").is_file()
    assert (site / "assets" / "site.css").is_file()
    assert (site / "assets" / "gis-findings.geojson").is_file()
