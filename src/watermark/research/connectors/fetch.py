"""URL-fetch connector for the research layer.

Fetches the text content of an arbitrary URL with the standard cached_get
discipline (on-disk cache + TTL + committed-fixture fallback).  HTML is
stripped to readable text; PDFs are extracted page by page.  Responses are
capped at ``settings.research_fetch_max_chars`` (default 20 000 characters).

Like the Serper connector, the cache and fixture paths work without live
network access, keeping CI and tests hermetic.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, cast

import httpx

from watermark.connectors._cache import DEFAULT_CACHE_TTL_HOURS, cached_get
from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

_CONNECTOR = "fetch"

_SKIP_TAGS = frozenset(
    {"script", "style", "head", "nav", "footer", "aside", "header", "noscript", "svg"}
)
_BLOCK_TAGS = frozenset(
    {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "td", "br", "section", "article"}
)


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML→plain-text stripper (no external deps)."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text + " ")

    def get_text(self) -> str:
        joined = "".join(self._parts)
        return re.sub(r"\n{3,}", "\n\n", re.sub(r" {2,}", " ", joined)).strip()


def _html_to_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _pdf_to_text(content: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages[:50]:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def fetch_url(
    url: str,
    *,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    settings: Settings | None = None,
) -> str:
    """Fetch a URL and return its readable text content (capped at max_chars).

    HTML is stripped to plain text; PDFs are extracted page-by-page (up to 50
    pages).  The response is capped at ``settings.research_fetch_max_chars``
    (default 20 000 characters).

    The HTTP request is only made on a live (non-offline, cache-miss) path —
    the cache and committed-fixture paths work without credentials or network
    access, so CI stays hermetic.

    Args:
        url:       Absolute URL to fetch.
        ttl_hours: Cache freshness window (default: 7 days).
        settings:  Supply explicitly in tests; omit to use ``get_settings()``.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()

    params: dict[str, Any] = {"url": url}

    def _live() -> str:
        try:
            resp = httpx.get(
                url,
                follow_redirects=True,
                timeout=settings.civic_request_timeout_s,
                headers={
                    "User-Agent": "watermark-bosc/1.0 (research; +https://github.com/watermark-directory)"
                },
            )
            resp.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("research.fetch_url.failed", url=url, error=str(exc))
            return ""

        ct = resp.headers.get("content-type", "").lower()
        if "pdf" in ct or url.lower().endswith(".pdf"):
            try:
                text = _pdf_to_text(resp.content)
            except Exception as exc:
                log.warning("research.fetch_url.pdf_error", url=url, error=str(exc))
                text = ""
        else:
            try:
                text = _html_to_text(resp.text)
            except Exception as exc:
                log.warning("research.fetch_url.html_error", url=url, error=str(exc))
                text = resp.text[: settings.research_fetch_max_chars]

        return text[: settings.research_fetch_max_chars]

    return cast(
        "str",
        cached_get(
            _CONNECTOR,
            params,
            _live,
            cache_dir=settings.research_cache_dir,
            offline=settings.research_offline,
            fixtures_dir=settings.research_fixtures_dir,
            ttl_hours=ttl_hours,
        ),
    )
