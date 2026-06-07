"""Load the site navigation + metadata from ``nav.yaml``.

The nav was the ``nav:`` block of the old mkdocs.yml; it now lives beside this
module as the single source of truth. :func:`load_nav` parses the nested
list/dict structure into a typed tree of :class:`NavNode`, which
:mod:`bosc.site.render` turns into the sidebar on every page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_NAV_YAML = Path(__file__).parent / "nav.yaml"


@dataclass(frozen=True)
class NavNode:
    """One nav entry: a leaf links a ``target`` page; a section holds children."""

    title: str
    target: str | None = None
    children: list[NavNode] = field(default_factory=list)

    @property
    def is_section(self) -> bool:
        return self.target is None


@dataclass(frozen=True)
class SiteNav:
    site_name: str
    site_description: str
    items: list[NavNode]

    def targets(self) -> list[str]:
        """Every leaf target in document order (for completeness checks)."""
        out: list[str] = []

        def walk(nodes: list[NavNode]) -> None:
            for n in nodes:
                if n.target is not None:
                    out.append(n.target)
                walk(n.children)

        walk(self.items)
        return out


def _parse_items(raw: list[object]) -> list[NavNode]:
    """Parse a nav list. Each item is ``{Title: target}`` or ``{Title: [children]}``."""
    nodes: list[NavNode] = []
    for item in raw:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError(f"nav entry must be a single-key mapping, got: {item!r}")
        ((title, value),) = item.items()
        if isinstance(value, str):
            nodes.append(NavNode(title=str(title), target=value))
        elif isinstance(value, list):
            nodes.append(NavNode(title=str(title), children=_parse_items(value)))
        else:
            raise ValueError(f"nav value for {title!r} must be a string or list, got: {value!r}")
    return nodes


def load_nav(path: Path | None = None) -> SiteNav:
    """Read ``nav.yaml`` into a :class:`SiteNav`."""
    data = yaml.safe_load((path or _NAV_YAML).read_text(encoding="utf-8"))
    return SiteNav(
        site_name=str(data["site_name"]).strip(),
        site_description=str(data.get("site_description", "")).strip(),
        items=_parse_items(data["nav"]),
    )
