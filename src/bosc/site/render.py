"""Render the generated ``web/`` markdown tree into a static HTML site under ``site/``.

This replaces the old MkDocs + ``custommill`` step. :func:`bosc.site.build.build_site`
still stages ``web/`` (markdown mirrored at repo-relative paths + generated pages);
this module walks that tree and:

* converts each ``*.md`` with Python-Markdown using the *same* extension stack the
  old ``mkdocs.yml`` used (admonitions, tables, toc, attr_list, md_in_html,
  pymdownx details + superfences with a ``mermaid`` custom fence), so page bodies
  render identically — only the surrounding chrome changes;
* wraps the body in a Jinja2 shell (sidebar nav from :mod:`bosc.site.nav`, a TOC,
  the ``extra.css`` evidence-tag styles, and a CDN Mermaid + ``mermaid-init.js``);
* rewrites internal ``*.md`` links to ``*.html`` (and the landing ``home.md`` to
  the root ``index.html``);
* copies every non-markdown file (CSS/JS, GeoJSON, CSVs, exhibit PDFs) verbatim.

The output is plain multipage HTML — no iframe, no hash routing — so GitHub Pages
just serves the files. Both ``web/`` and ``site/`` are git-ignored and regenerable.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from pymdownx.superfences import fence_code_format

from bosc.logging import get_logger
from bosc.site.nav import NavNode, SiteNav, load_nav

log = get_logger(__name__)

_TEMPLATES = Path(__file__).parent / "templates"

# Mirror the old mkdocs.yml `markdown_extensions` exactly so bodies render the same.
_MD_EXTENSIONS = [
    "admonition",
    "attr_list",
    "md_in_html",
    "tables",
    "toc",
    "pymdownx.details",
    "pymdownx.superfences",
]
_MD_EXTENSION_CONFIGS: dict[str, dict[str, Any]] = {
    "toc": {"permalink": True},
    "pymdownx.superfences": {
        "custom_fences": [
            {"name": "mermaid", "class": "mermaid", "format": fence_code_format},
        ],
    },
}

_HREF_RE = re.compile(r'(href|src)="([^"]*)"')
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass
class RenderResult:
    site_dir: Path
    pages: int = 0
    assets: int = 0


def _rewrite_target(url: str) -> str:
    """Rewrite one link/asset URL: internal ``*.md`` -> ``*.html`` (``home.md`` -> index).

    Absolute URLs (``https:``, ``mailto:``, protocol-relative), in-page anchors,
    and non-markdown links are returned unchanged — so the pre-existing links into
    unpublished ``data/documents/**`` behave exactly as before.
    """
    if not url or url.startswith("#") or url.startswith("//") or _SCHEME_RE.match(url):
        return url
    base, hash_sep, frag = url.partition("#")
    path, q_sep, query = base.partition("?")
    if path.endswith(".md"):
        path = "index.html" if path == "home.md" else path[:-3] + ".html"
    return f"{path}{q_sep}{query}{hash_sep}{frag}"


def _rewrite_links(html: str) -> str:
    """Apply :func:`_rewrite_target` to every ``href``/``src`` in rendered HTML."""

    def repl(m: re.Match[str]) -> str:
        return f'{m.group(1)}="{_rewrite_target(m.group(2))}"'

    return _HREF_RE.sub(repl, html)


def _output_rel(src_rel: Path) -> Path:
    """Map a ``web/``-relative markdown path to its ``site/``-relative HTML path."""
    if src_rel == Path("home.md"):
        return Path("index.html")
    return src_rel.with_suffix(".html")


def _path_to_root(out_rel: Path) -> str:
    """Relative prefix from a page back to the site root (e.g. ``../../`` ), or ``""``."""
    depth = len(out_rel.parts) - 1
    return "../" * depth


def _nav_html(items: list[NavNode], root: str, current: str) -> Markup:
    """Render the sidebar nav for the page whose ``web/``-relative target is ``current``."""
    parts: list[str] = ["<ul>"]
    for node in items:
        if node.is_section:
            parts.append('<li class="nav-section">')
            parts.append(f'<span class="nav-section-title">{Markup.escape(node.title)}</span>')
            parts.append(str(_nav_html(node.children, root, current)))
            parts.append("</li>")
        else:
            assert node.target is not None
            href = root + _rewrite_target(node.target)
            active = " active" if node.target == current else ""
            parts.append(
                f'<li class="nav-leaf{active}">'
                f'<a href="{Markup.escape(href)}">{Markup.escape(node.title)}</a></li>'
            )
    parts.append("</ul>")
    return Markup("".join(parts))


def render_site(
    web: Path,
    site: Path,
    *,
    nav: SiteNav | None = None,
) -> RenderResult:
    """Render the ``web/`` markdown tree into a static HTML site at ``site/``."""
    nav = nav or load_nav()
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("base.html")
    md = markdown.Markdown(extensions=_MD_EXTENSIONS, extension_configs=_MD_EXTENSION_CONFIGS)

    result = RenderResult(site_dir=site)
    for path in sorted(web.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(web)
        if path.suffix == ".md":
            out_rel = _output_rel(rel)
            out = site / out_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            text = path.read_text(encoding="utf-8")
            md.reset()
            body = _rewrite_links(md.convert(text))
            root = _path_to_root(out_rel)
            page_title = _first_heading(text) or nav.site_name
            out.write_text(
                template.render(
                    site_name=nav.site_name,
                    site_description=nav.site_description,
                    page_title=page_title,
                    content=Markup(body),
                    # `toc` is attached to the Markdown instance by the toc extension.
                    toc=Markup(getattr(md, "toc", "")),
                    nav_html=_nav_html(nav.items, root, current=rel.as_posix()),
                    root=root,
                    is_home=(out_rel == Path("index.html")),
                ),
                encoding="utf-8",
            )
            result.pages += 1
        else:
            out = site / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
            result.assets += 1

    log.info("site.rendered", site=str(site), pages=result.pages, assets=result.assets)
    return result


_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _first_heading(text: str) -> str | None:
    """The page's first ``# H1`` as a plain title, if any."""
    m = _H1_RE.search(text)
    if not m:
        return None
    # Strip simple inline markdown/emphasis markers for a clean <title>.
    return re.sub(r"[*_`]", "", m.group(1)).strip()
