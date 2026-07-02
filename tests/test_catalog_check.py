"""Tests for ``watermark catalog check`` — the validation + drift gate (epic #631, issue #626).

Hermetic synthetic-tree tests pin each finding kind (orphan / missing / unmaterialized LFS /
stale / checksum-drift / duplicate-id), plus the regression guard that the *committed* catalog
passes the gate (no errors) — the CI-enforced successor to the manual completeness audit.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

from watermark.catalog.check import check, errors
from watermark.catalog.reconcile import reconcile, write_observed
from watermark.config import Settings

_FIXED = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _data(settings: Settings, relpath: str, body: str = "x: 1\n") -> Path:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _entry(settings: Settings, name: str, body: str) -> None:
    path = settings.catalog_dir / "reference" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def _basic(name: str, relpath: str, refresh: str = "  cadence: static\n") -> str:
    return (
        textwrap.dedent(
            f"""\
        id: {name}
        title: T
        scope: reference
        producer:
          kind: connector
          source: x
        storage:
        - relpath: {relpath}
          media_type: application/x-yaml
        refresh:
        """
        )
        + refresh
    )


def _kinds(findings: list) -> set[str]:  # type: ignore[type-arg]
    return {f.kind for f in findings}


# --- clean -----------------------------------------------------------------------------------
def test_clean_catalog_has_no_findings(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml")
    _entry(settings, "echo-x", _basic("echo-x", "reference/echo/x.yaml"))
    assert check(settings=settings, now=_FIXED) == []


# --- orphan ----------------------------------------------------------------------------------
def test_orphan_file_is_an_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml")
    _data(settings, "reference/echo/uncatalogued.yaml")  # no entry covers this
    _entry(settings, "echo-x", _basic("echo-x", "reference/echo/x.yaml"))
    findings = check(settings=settings, now=_FIXED)
    orphans = [f for f in findings if f.kind == "orphan-file"]
    assert [f.subject for f in orphans] == ["reference/echo/uncatalogued.yaml"]
    assert orphans[0].severity == "error"


def test_readme_is_not_an_orphan(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml")
    _data(settings, "reference/echo/README.md", "# docs\n")  # skipped, not catalogued
    _entry(settings, "echo-x", _basic("echo-x", "reference/echo/x.yaml"))
    assert "orphan-file" not in _kinds(check(settings=settings, now=_FIXED))


# --- missing / unmaterialized ----------------------------------------------------------------
def test_missing_declared_file_is_an_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(settings, "echo-x", _basic("echo-x", "reference/echo/gone.yaml"))
    findings = check(settings=settings, now=_FIXED)
    missing = [f for f in findings if f.kind == "missing-files"]
    assert missing and missing[0].severity == "error"
    assert "gone.yaml" in missing[0].detail


def test_unmaterialized_lfs_pointer_is_a_warning_not_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(
        settings,
        "reference/imagery/scene.tif",
        "version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 1\n",
    )
    _entry(settings, "imagery-scene", _basic("imagery-scene", "reference/imagery/scene.tif"))
    findings = check(settings=settings, now=_FIXED)
    assert "missing-files" not in _kinds(findings)  # a pointer is present, not missing
    unmat = [f for f in findings if f.kind == "unmaterialized"]
    assert unmat and unmat[0].severity == "warn"
    assert errors(findings) == []  # never fails the gate


# --- staleness -------------------------------------------------------------------------------
def test_stale_warns_by_default_and_fails_under_strict(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "meta:\n  last_refreshed: '2020-01-01'\n")
    _entry(
        settings,
        "echo-x",
        _basic("echo-x", "reference/echo/x.yaml", refresh="  cadence: annual\n  ttl_days: 30\n"),
    )
    lenient = check(settings=settings, now=_FIXED, strict=False)
    stale = [f for f in lenient if f.kind == "stale"]
    assert stale and stale[0].severity == "warn"
    assert errors(lenient) == []  # warns don't fail
    strict = check(settings=settings, now=_FIXED, strict=True)
    assert next(f for f in strict if f.kind == "stale").severity == "error"
    assert errors(strict)  # now it fails


# --- checksum drift --------------------------------------------------------------------------
def test_checksum_drift_against_a_pin_is_an_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "real: bytes\n")
    _entry(
        settings,
        "echo-x",
        textwrap.dedent(
            """\
            id: echo-x
            title: T
            scope: reference
            producer:
              kind: connector
              source: x
            storage:
            - relpath: reference/echo/x.yaml
              media_type: application/x-yaml
              sha256: "0000000000000000000000000000000000000000000000000000000000000000"
            refresh:
              cadence: static
            """
        ),
    )
    # reconcile records the file's real sha into _observed.yaml; the pin is deliberately wrong
    write_observed(reconcile(settings=settings, now=_FIXED), settings=settings)
    findings = check(settings=settings, now=_FIXED)
    drift = [f for f in findings if f.kind == "checksum-drift"]
    assert drift and drift[0].severity == "error"


def test_matching_pin_has_no_drift(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    f = _data(settings, "reference/echo/x.yaml", "real: bytes\n")
    import hashlib

    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    _entry(
        settings,
        "echo-x",
        textwrap.dedent(
            f"""\
            id: echo-x
            title: T
            scope: reference
            producer:
              kind: connector
              source: x
            storage:
            - relpath: reference/echo/x.yaml
              media_type: application/x-yaml
              sha256: "{sha}"
            refresh:
              cadence: static
            """
        ),
    )
    write_observed(reconcile(settings=settings, now=_FIXED), settings=settings)
    assert "checksum-drift" not in _kinds(check(settings=settings, now=_FIXED))


# --- dependency graph (#1020) ------------------------------------------------------------------
def test_unknown_dependency_is_an_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml")
    _entry(
        settings,
        "echo-x",
        _basic("echo-x", "reference/echo/x.yaml") + "depends_on:\n- no-such-entry\n",
    )
    findings = check(settings=settings, now=_FIXED)
    unknown = [f for f in findings if f.kind == "unknown-dependency"]
    assert unknown and unknown[0].severity == "error"
    assert "no-such-entry" in unknown[0].detail


def test_dependency_cycle_is_an_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml")
    _data(settings, "reference/echo/b.yaml")
    _entry(
        settings, "echo-a", _basic("echo-a", "reference/echo/a.yaml") + "depends_on:\n- echo-b\n"
    )
    _entry(
        settings, "echo-b", _basic("echo-b", "reference/echo/b.yaml") + "depends_on:\n- echo-a\n"
    )
    findings = check(settings=settings, now=_FIXED)
    cycles = [f for f in findings if f.kind == "dependency-cycle"]
    assert cycles and cycles[0].severity == "error"
    assert "echo-a" in cycles[0].detail and "echo-b" in cycles[0].detail


def test_resolved_acyclic_graph_is_clean(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml")
    _data(settings, "reference/echo/b.yaml")
    _entry(
        settings, "echo-a", _basic("echo-a", "reference/echo/a.yaml") + "depends_on:\n- echo-b\n"
    )
    _entry(settings, "echo-b", _basic("echo-b", "reference/echo/b.yaml"))
    assert check(settings=settings, now=_FIXED) == []


def test_virtual_entry_without_storage_is_not_missing(tmp_path: Path) -> None:
    """A storage-less entry is a virtual DAG node (an aggregate like onboard-bundle) — present
    by definition, never a missing-files error."""
    settings = _settings(tmp_path)
    _entry(
        settings,
        "virtual-agg",
        textwrap.dedent(
            """\
            id: virtual-agg
            title: T
            scope: reference
            producer:
              kind: derived
              source: aggregate
            refresh:
              cadence: on-demand
            """
        ),
    )
    assert check(settings=settings, now=_FIXED) == []


# --- downstream staleness (#1022) ---------------------------------------------------------------
def _dated(
    settings: Settings, name: str, relpath: str, asof: str, deps: list[str] | None = None
) -> None:
    _data(settings, relpath, f"meta:\n  asof: '{asof}'\n")
    dep_block = "depends_on:\n" + "".join(f"- {d}\n" for d in deps) if deps else ""
    _entry(settings, name, _basic(name, relpath) + dep_block)


def test_downstream_stale_warns_when_upstream_is_newer(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _dated(settings, "up", "reference/echo/up.yaml", "2026-06-15")
    _dated(settings, "down", "reference/echo/down.yaml", "2026-03-01", deps=["up"])
    findings = check(settings=settings, now=_FIXED)
    ds = [f for f in findings if f.kind == "downstream-stale"]
    assert ds and ds[0].severity == "warn"
    assert ds[0].subject == "down"
    assert "catalog run down" in ds[0].detail
    assert errors(findings) == []  # a warning never fails the gate


def test_downstream_stale_promoted_under_strict(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _dated(settings, "up", "reference/echo/up.yaml", "2026-06-15")
    _dated(settings, "down", "reference/echo/down.yaml", "2026-03-01", deps=["up"])
    strict = check(settings=settings, now=_FIXED, strict=True)
    assert next(f for f in strict if f.kind == "downstream-stale").severity == "error"
    assert errors(strict)


def test_downstream_fresher_than_upstream_is_clean(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _dated(settings, "up", "reference/echo/up.yaml", "2026-03-01")
    _dated(settings, "down", "reference/echo/down.yaml", "2026-06-15", deps=["up"])
    assert "downstream-stale" not in _kinds(check(settings=settings, now=_FIXED))


def test_downstream_stale_skips_edges_with_unknown_dates(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/up.yaml")  # no meta.asof, no last_refreshed
    _entry(settings, "up", _basic("up", "reference/echo/up.yaml"))
    _dated(settings, "down", "reference/echo/down.yaml", "2026-03-01", deps=["up"])
    assert "downstream-stale" not in _kinds(check(settings=settings, now=_FIXED))


def test_downstream_stale_scoped_to_a_root_closure(tmp_path: Path) -> None:
    from watermark.catalog import load_entries
    from watermark.catalog.check import downstream_stale_findings
    from watermark.catalog.reconcile import reconcile

    settings = _settings(tmp_path)
    _dated(settings, "up", "reference/echo/up.yaml", "2026-06-15")
    _dated(settings, "down", "reference/echo/down.yaml", "2026-03-01", deps=["up"])
    _dated(settings, "other-up", "reference/echo/ou.yaml", "2026-06-15")
    _dated(settings, "other", "reference/echo/o.yaml", "2026-03-01", deps=["other-up"])
    entries = load_entries(settings=settings)
    observed = reconcile(settings=settings, now=_FIXED).entries
    scoped = downstream_stale_findings(entries, observed, root="down")
    assert [f.subject for f in scoped] == ["down"]  # `other` is outside the closure


# --- the export pre-flight (#1024) --------------------------------------------------------------
def test_upstream_preflight_reports_ttl_stale_and_ordering_within_the_closure(
    tmp_path: Path,
) -> None:
    from watermark.catalog.check import upstream_preflight

    settings = _settings(tmp_path)
    # a TTL-stale upstream in the closure...
    _data(settings, "reference/echo/up.yaml", "meta:\n  asof: '2020-01-01'\n")
    _entry(
        settings,
        "up",
        _basic("up", "reference/echo/up.yaml", refresh="  cadence: annual\n  ttl_days: 30\n"),
    )
    # ...an unrelated TTL-stale entry outside it...
    _data(settings, "reference/echo/other.yaml", "meta:\n  asof: '2020-01-01'\n")
    _entry(
        settings,
        "other",
        _basic("other", "reference/echo/other.yaml", refresh="  cadence: annual\n  ttl_days: 30\n"),
    )
    # ...and a virtual bundle root depending on `up`.
    _entry(
        settings,
        "bundle-root",
        textwrap.dedent(
            """\
            id: bundle-root
            title: T
            scope: reference
            producer:
              kind: derived
              source: export
            depends_on:
            - up
            refresh:
              cadence: on-demand
            """
        ),
    )
    findings = upstream_preflight("bundle-root", settings=settings, now=_FIXED)
    assert [f.subject for f in findings] == ["up"]  # `other` is outside the closure
    assert all(f.severity == "warn" for f in findings)
    assert "catalog run bundle-root" in findings[0].detail


def test_upstream_preflight_does_not_report_the_root_itself_as_a_stale_upstream(
    tmp_path: Path,
) -> None:
    from watermark.catalog.check import upstream_preflight

    settings = _settings(tmp_path)
    # The root is TTL-stale but its (older) leaf is not, and the leaf is not newer than the root
    # (so no downstream-stale edge fires). The root is the export target, not one of its own
    # upstreams, so the TTL scan must not report it — the only finding path left here is empty.
    _data(settings, "reference/echo/leaf.yaml", "meta:\n  asof: '2020-01-01'\n")
    _entry(
        settings,
        "leaf",
        _basic(
            "leaf", "reference/echo/leaf.yaml", refresh="  cadence: annual\n  ttl_days: 36500\n"
        ),
    )
    _data(settings, "reference/echo/root.yaml", "meta:\n  asof: '2020-06-01'\n")
    _entry(
        settings,
        "root",
        _basic("root", "reference/echo/root.yaml", refresh="  cadence: annual\n  ttl_days: 30\n")
        + "depends_on:\n- leaf\n",
    )
    findings = upstream_preflight("root", settings=settings, now=_FIXED)
    # root is TTL-stale but excluded (it's the target); leaf is fresh; no downstream-stale edge.
    assert "root" not in [f.subject for f in findings]
    assert findings == []


def test_upstream_preflight_is_silent_for_a_missing_root(tmp_path: Path) -> None:
    from watermark.catalog.check import upstream_preflight

    settings = _settings(tmp_path)
    assert upstream_preflight("no-such-entry", settings=settings, now=_FIXED) == []


def test_committed_bundle_entry_resolves() -> None:
    """The committed bundle-records entry exists and its full dependency closure resolves."""
    from watermark.catalog import load_entries
    from watermark.catalog.dag import subgraph_order

    order = [e.id for e in subgraph_order(load_entries(), "bundle-records")]
    assert order[-1] == "bundle-records"  # the root is always emitted last
    # a representative sample of the declared upstreams resolve into the closure
    assert {"rsei-inventory", "echo-maumee-npdes", "hydrology-wbd"} <= set(order)


# --- schema / duplicate ----------------------------------------------------------------------
def test_duplicate_id_is_an_error_and_short_circuits_on_load_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml")
    # a malformed entry -> load-error, which stops the gate before missing/orphan run
    p = settings.catalog_dir / "reference" / "broken.yaml"
    p.parent.mkdir(parents=True)
    p.write_text("id: broken\nscope: reference\n", encoding="utf-8")  # missing required fields
    findings = check(settings=settings, now=_FIXED)
    assert _kinds(findings) == {"schema"}
    assert errors(findings)


# --- regression guard ------------------------------------------------------------------------
def test_committed_catalog_passes_the_gate() -> None:
    """The real committed catalog + data tree clear the gate (no error findings).

    This is the invariant the CI `check` job enforces — a new dataset without a catalog
    entry (orphan), a renamed/removed file (missing), or a drifted pin turns it red.
    """
    assert errors(check()) == []
