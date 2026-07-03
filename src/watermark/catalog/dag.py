"""The catalog's dependency graph — pure graph operations over ``depends_on`` (#1020).

``CatalogEntry.depends_on`` turns the catalog into a process DAG: each edge says "produce
that entry before regenerating this one". This module holds the graph primitives shared by
the two consumers — ``watermark catalog check`` gates referential integrity + acyclicity here,
and ``watermark catalog run`` (:mod:`watermark.catalog.runner`, #1021) resolves the upstream-first
execution order. Everything operates on an already-loaded entry list; no file I/O.
"""

from __future__ import annotations

from watermark.catalog import CatalogEntry


def by_id(entries: list[CatalogEntry]) -> dict[str, CatalogEntry]:
    """Index the loaded catalog by entry id (duplicate ids are `check`'s problem, not ours)."""
    return {entry.id: entry for entry in entries}


def unknown_dependencies(entries: list[CatalogEntry]) -> list[tuple[str, str]]:
    """Every ``(entry_id, dep_id)`` whose ``dep_id`` resolves to no catalog entry (sorted)."""
    ids = set(by_id(entries))
    return sorted(
        (entry.id, dep) for entry in entries for dep in entry.depends_on if dep not in ids
    )


def find_cycle(entries: list[CatalogEntry]) -> list[str] | None:
    """The first dependency cycle as a closed path (``[a, b, …, a]``), or ``None``.

    Deterministic: nodes and edges are visited in sorted order, so the same catalog always
    reports the same cycle. Unresolved dependency ids are skipped — they are a separate
    :func:`unknown_dependencies` finding, not a graph edge.
    """
    index = by_id(entries)
    # 0 = unvisited, 1 = on the current DFS stack, 2 = done
    state: dict[str, int] = dict.fromkeys(index, 0)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for dep in sorted(index[node].depends_on):
            if dep not in index:
                continue
            if state[dep] == 1:  # back edge — close the cycle from dep's stack position
                return [*stack[stack.index(dep) :], dep]
            if state[dep] == 0:
                found = visit(dep)
                if found is not None:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(index):
        if state[node] == 0:
            cycle = visit(node)
            if cycle is not None:
                return cycle
    return None


def subgraph_order(entries: list[CatalogEntry], root_id: str) -> list[CatalogEntry]:
    """The DAG rooted at ``root_id`` in upstream-first topological order (root last).

    Depth-first postorder over ``depends_on``, deterministic (sorted edges). Raises
    ``KeyError`` for an unknown root or dependency id and ``ValueError`` on a cycle — run
    ``watermark catalog check`` first; this function assumes a gate-clean graph.
    """
    index = by_id(entries)
    if root_id not in index:
        raise KeyError(f"unknown catalog entry {root_id!r}")
    order: list[CatalogEntry] = []
    state: dict[str, int] = {}  # 1 = on stack, 2 = emitted

    def visit(node: str, path: list[str]) -> None:
        if node not in index:
            raise KeyError(f"{path[-1]}: depends_on names unknown entry {node!r}")
        if state.get(node) == 1:
            cycle = [*path[path.index(node) :], node]
            raise ValueError(f"dependency cycle: {' -> '.join(cycle)}")
        if state.get(node) == 2:
            return
        state[node] = 1
        for dep in sorted(index[node].depends_on):
            visit(dep, [*path, node])
        state[node] = 2
        order.append(index[node])

    visit(root_id, [])
    return order
