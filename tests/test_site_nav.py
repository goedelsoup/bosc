"""Guard: every nav target must resolve in the generated site.

The nav (``src/bosc/site/nav.yaml``) is hand-maintained while build scripts
reorganize the corpus, so a moved/renamed extraction silently breaks a nav link.
This builds the site once and asserts every nav ``*.md`` target exists under
``web/`` — covering both source-mirrored pages and generated ones.
"""

from __future__ import annotations

from pathlib import Path

from bosc.config import Settings
from bosc.site.build import build_site
from bosc.site.nav import load_nav

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_every_nav_target_resolves(tmp_path: Path) -> None:
    targets = [t for t in load_nav().targets() if t.endswith(".md")]
    assert targets, "no nav targets parsed"

    web = tmp_path / "web"
    build_site(settings=Settings(data_dir=REPO_ROOT / "data"), web_dir=web)

    missing = [t for t in targets if not (web / t).is_file()]
    assert not missing, f"nav points at pages absent from the built site: {missing}"
