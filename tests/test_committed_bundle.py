"""The committed-bundle drift check and its lean-trim writer (#2025).

These run against a synthetic bundle pair rather than a real export: the comparison logic is
what's under test, and a real ``export_bundle()`` is the suite's most expensive operation (see
``tests/CLAUDE.md``). The end-to-end half — that a real committed bundle still tracks a real
export — is ``test_committed_bundle_tracks_its_export`` in ``test_site_bundle.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from watermark.site.committed import (
    RETRIEVAL_FEEDS,
    _apply_lean_trim,
    _compare_feeds,
    _compare_manifests,
    _keeps_retrieval_feeds,
)


def _write_bundle(
    root: Path,
    slug: str,
    feeds: dict[str, list[dict[str, Any]]],
    *,
    generated_at: str = "2026-01-01T00:00:00+00:00",
    readiness: dict[str, Any] | None = None,
    contract: str = "2.2.0",
    with_schemas: bool = False,
) -> Path:
    """A minimal bundle on disk: one JSON array file per feed plus a manifest that describes it."""
    bundle = root / slug
    (bundle / "feeds").mkdir(parents=True, exist_ok=True)
    refs = []
    for name, rows in feeds.items():
        path = f"feeds/{name}.json"
        (bundle / path).write_text(
            json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        refs.append(
            {
                "name": name,
                "path": path,
                "media_type": "application/json",
                "schema_ref": f"schemas/{name}.schema.json",
                "kind": "collection",
                "count": len(rows),
            }
        )
    if with_schemas:
        (bundle / "schemas").mkdir(exist_ok=True)
        (bundle / "schemas" / "manifest.schema.json").write_text("{}", encoding="utf-8")
    manifest = {
        "site": slug,
        "contract_version": contract,
        "generated_at": generated_at,
        "feed_count": len(refs),
        "row_total": sum(r["count"] for r in refs),
        "readiness": readiness or {"tier": "stub", "domains": {}},
        "feeds": refs,
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return bundle


def _manifest(bundle: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    return parsed


def test_an_unchanged_bundle_reports_nothing(tmp_path: Path) -> None:
    """Two exports of an unchanged corpus differ only in ``generated_at``, which is never a
    finding — otherwise every check would be a false positive and the tool would be ignored."""
    rows = {"records": [{"rel": "a.yaml"}], "timeline": [{"date": "2026-01-01"}]}
    committed = _write_bundle(tmp_path / "c", "lima", rows, generated_at="2026-01-01T00:00:00Z")
    fresh = _write_bundle(tmp_path / "f", "lima", rows, generated_at="2026-08-13T19:00:00Z")

    findings = _compare_manifests("lima", _manifest(committed), _manifest(fresh)) + _compare_feeds(
        "lima", committed, fresh, _manifest(committed), _manifest(fresh)
    )
    assert findings == []


def test_a_row_count_that_moved_is_a_count_finding(tmp_path: Path) -> None:
    """The #2022 shape: the corpus grew and the bundle didn't. Reported per feed, with both
    numbers, because "which feed and by how much" is what decides whether a drop needs explaining
    before it is accepted."""
    committed = _write_bundle(tmp_path / "c", "lima", {"records": [{"rel": "a.yaml"}]})
    fresh = _write_bundle(
        tmp_path / "f", "lima", {"records": [{"rel": "a.yaml"}, {"rel": "b.yaml"}]}
    )

    (finding,) = _compare_feeds("lima", committed, fresh, _manifest(committed), _manifest(fresh))
    assert finding.kind == "count"
    assert finding.subject == "records"
    assert "1 rows != fresh 2" in finding.detail


def test_a_changed_figure_that_moves_no_count_is_still_caught(tmp_path: Path) -> None:
    """The reason the check compares BYTES and not just counts.

    A corrected value inside an existing row — a re-pulled dataset's sha256 in the ``catalog``
    feed, a revised figure in a record — leaves every count identical. 23 of the 26 committed
    bundles were stale on exactly this shape when the check first ran: they published a size and
    hash for a shared dataset that had since changed.
    """
    committed = _write_bundle(tmp_path / "c", "lima", {"catalog": [{"id": "x", "sha": "old"}]})
    fresh = _write_bundle(tmp_path / "f", "lima", {"catalog": [{"id": "x", "sha": "new"}]})

    (finding,) = _compare_feeds("lima", committed, fresh, _manifest(committed), _manifest(fresh))
    assert finding.kind == "content"
    assert finding.subject == "catalog"
    # The report names the row and the field, so the reader knows what moved without a diff.
    assert "row 0" in finding.detail and "sha" in finding.detail


def test_a_feed_the_bundle_lacks_and_one_it_should_not_carry(tmp_path: Path) -> None:
    """Both directions. The existing suite guard is a *subset* assertion — it catches a feed the
    exporter no longer produces and is blind to one the bundle is missing, which is how Fort Wayne
    shipped without ``drawdown`` while passing at the current contract (#1791)."""
    committed = _write_bundle(tmp_path / "c", "lima", {"records": [], "retired": []})
    fresh = _write_bundle(tmp_path / "f", "lima", {"records": [], "grid": [{"mw": 1}]})

    by_kind = {
        f.kind: f
        for f in _compare_feeds("lima", committed, fresh, _manifest(committed), _manifest(fresh))
    }
    assert by_kind["missing-feed"].subject == "grid"
    assert by_kind["stale-feed"].subject == "retired"


def test_readiness_and_contract_drift_are_manifest_findings(tmp_path: Path) -> None:
    """Readiness is a standing property recomputed at every export, so a snapshot can over- or
    under-read its own evidence (#1770 — Urbana shipped ``record: live`` over a zero-length feed)."""
    committed = _write_bundle(
        tmp_path / "c",
        "lima",
        {"records": []},
        readiness={"tier": "stub", "domains": {}},
        contract="2.0.0",
    )
    fresh = _write_bundle(
        tmp_path / "f",
        "lima",
        {"records": []},
        readiness={"tier": "case", "domains": {}},
        contract="2.2.0",
    )

    subjects = {
        f.subject for f in _compare_manifests("lima", _manifest(committed), _manifest(fresh))
    }
    assert {"readiness", "contract_version"} <= subjects


def test_a_declared_feed_whose_file_is_absent(tmp_path: Path) -> None:
    """A manifest that declares a feed whose file is gone makes the static Astro build ENOENT, so
    it is reported as its own kind rather than as a count or content difference."""
    committed = _write_bundle(tmp_path / "c", "lima", {"records": [{"rel": "a.yaml"}]})
    (committed / "feeds" / "records.json").unlink()
    fresh = _write_bundle(tmp_path / "f", "lima", {"records": [{"rel": "a.yaml"}]})

    (finding,) = _compare_feeds("lima", committed, fresh, _manifest(committed), _manifest(fresh))
    assert finding.kind == "file"


def test_the_lean_trim_drops_schemas_and_the_retrieval_indexes(tmp_path: Path) -> None:
    """A committed bundle is not a raw export: no ``schemas/`` (the contract lives once at
    ``data/site/bundle/schemas/``) and no page-level retrieval indexes — files AND manifest rows,
    since declaring a feed whose file is absent breaks the build."""
    bundle = _write_bundle(
        tmp_path / "b",
        "lima",
        {"records": [{"rel": "a.yaml"}], "passages": [{"id": "p1"}, {"id": "p2"}]},
        with_schemas=True,
    )
    _apply_lean_trim(bundle, keep_retrieval=False)

    manifest = _manifest(bundle)
    assert not (bundle / "schemas").exists()
    assert not (bundle / "feeds" / "passages.json").exists()
    assert {f["name"] for f in manifest["feeds"]} == {"records"}
    # The totals must be recomputed, not left describing the untrimmed export.
    assert manifest["feed_count"] == 1
    assert manifest["row_total"] == 1


def test_the_retained_set_is_read_off_the_committed_manifest(tmp_path: Path) -> None:
    """Which sites keep their ``passages`` index is derived, never listed.

    ``web/sites/README.md`` carried the exception set as prose and said of it: "it went stale
    within one issue of being written." Running the drop step across a stale list has silently
    deleted committed retrieval evidence twice (#1969, #1993). So the tree describes itself — a
    site keeps its retrieval indexes iff its own committed manifest already declares them.
    """
    keeps = _write_bundle(tmp_path / "a", "van-wert", {"records": [], "passages": [{"id": "p"}]})
    lean = _write_bundle(tmp_path / "b", "toledo", {"records": []})
    absent = tmp_path / "c" / "brand-new"

    assert _keeps_retrieval_feeds(keeps) is True
    assert _keeps_retrieval_feeds(lean) is False
    # A site with no committed bundle yet defaults to the lean shape rather than erroring.
    assert _keeps_retrieval_feeds(absent) is False


@pytest.mark.parametrize("feed", RETRIEVAL_FEEDS)
def test_keeping_the_retrieval_feeds_leaves_them_untouched(tmp_path: Path, feed: str) -> None:
    """The half that #1969 and #1993 got wrong: with the site opted in, the trim must not delete."""
    bundle = _write_bundle(tmp_path / "b", "van-wert", {"records": [], feed: [{"id": "p"}]})
    _apply_lean_trim(bundle, keep_retrieval=True)

    assert (bundle / "feeds" / f"{feed}.json").is_file()
    assert feed in {f["name"] for f in _manifest(bundle)["feeds"]}
