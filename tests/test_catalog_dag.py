"""Tests for the catalog dependency graph (epic #1019, issue #1020).

Pure graph-primitive tests over in-memory entries: referential integrity, cycle
detection (deterministic path), and the upstream-first topological order that
``watermark catalog run`` (#1021) executes.
"""

from __future__ import annotations

import pytest

from watermark.catalog import CatalogEntry, Producer, Refresh
from watermark.catalog.dag import find_cycle, subgraph_order, unknown_dependencies


def _entry(entry_id: str, depends_on: list[str] | None = None) -> CatalogEntry:
    return CatalogEntry(
        id=entry_id,
        title=entry_id,
        scope="reference",
        producer=Producer(kind="connector", source="x"),
        refresh=Refresh(cadence="on-demand"),
        depends_on=depends_on or [],
    )


# --- referential integrity ---------------------------------------------------------------
def test_unknown_dependencies_reports_each_unresolved_edge() -> None:
    entries = [_entry("a", ["b", "ghost"]), _entry("b", ["phantom"])]
    assert unknown_dependencies(entries) == [("a", "ghost"), ("b", "phantom")]


def test_resolved_graph_has_no_unknown_dependencies() -> None:
    assert unknown_dependencies([_entry("a", ["b"]), _entry("b")]) == []


# --- cycle detection ---------------------------------------------------------------------
def test_acyclic_graph_has_no_cycle() -> None:
    entries = [_entry("a", ["b", "c"]), _entry("b", ["c"]), _entry("c")]
    assert find_cycle(entries) is None


def test_self_loop_is_a_cycle() -> None:
    assert find_cycle([_entry("a", ["a"])]) == ["a", "a"]


def test_cycle_is_reported_as_a_closed_path() -> None:
    entries = [_entry("a", ["b"]), _entry("b", ["c"]), _entry("c", ["a"])]
    cycle = find_cycle(entries)
    assert cycle == ["a", "b", "c", "a"]


def test_unresolved_dependency_is_not_a_graph_edge() -> None:
    # `ghost` is unknown_dependencies' finding; it must not crash or fake a cycle here.
    assert find_cycle([_entry("a", ["ghost"])]) is None


# --- topological order -------------------------------------------------------------------
def test_subgraph_order_is_upstream_first_with_root_last() -> None:
    entries = [
        _entry("root", ["mid-1", "mid-2"]),
        _entry("mid-1", ["leaf"]),
        _entry("mid-2", ["leaf"]),
        _entry("leaf"),
        _entry("unrelated"),  # not reachable from root — excluded from the plan
    ]
    order = [e.id for e in subgraph_order(entries, "root")]
    assert order == ["leaf", "mid-1", "mid-2", "root"]


def test_shared_upstream_is_emitted_once() -> None:
    entries = [
        _entry("root", ["a", "b"]),
        _entry("a", ["shared"]),
        _entry("b", ["shared"]),
        _entry("shared"),
    ]
    order = [e.id for e in subgraph_order(entries, "root")]
    assert order.count("shared") == 1


def test_subgraph_order_raises_on_unknown_root_and_unknown_dep() -> None:
    with pytest.raises(KeyError):
        subgraph_order([_entry("a")], "nope")
    with pytest.raises(KeyError):
        subgraph_order([_entry("a", ["ghost"])], "a")


def test_subgraph_order_raises_on_cycle() -> None:
    entries = [_entry("a", ["b"]), _entry("b", ["a"])]
    with pytest.raises(ValueError, match="dependency cycle"):
        subgraph_order(entries, "a")


# --- the committed catalog ---------------------------------------------------------------
def test_committed_catalog_graph_is_resolved_and_acyclic() -> None:
    from watermark.catalog import load_entries

    entries = load_entries()
    assert unknown_dependencies(entries) == []
    assert find_cycle(entries) is None
