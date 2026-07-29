"""Guard on ``.test_durations`` — the manifest CI's shard balancer reads (#1772).

CI runs the suite across six runners (``pytest --splits 6 --group N``). pytest-split prices
each collected test at its duration in the committed ``.test_durations``, and prices anything
*missing* from that file at the **average** of the ones present. So an unrecorded test is not
ignored, it is mis-priced — and a file of slow unrecorded tests reads as cheap. At #1772 the
manifest held 1,206 entries for a suite collecting 2,520 tests: shard 6 looked like the
cheapest shard (15.4 s of recorded duration, on 343 tests) and in fact took 8m31s, 5.3x the
fastest shard. Since ``check`` waits on the slowest shard, that inversion set the wall time of
the whole backend gate. Nothing detected the drift, so this does.

It is a **coverage** gate, not a freshness one. A recorded duration that has drifted a little
still balances fine; a *missing* one is what inverts the ordering. Entries left behind by
deleted or renamed tests are harmless either way — pytest-split filters the manifest down to
the collected ids before averaging — so they are not gated on.

Regenerate the whole manifest with ``mise run test:durations``
(``uv run pytest -n0 --store-durations --clean-durations``). ``-n0`` is load-bearing:
durations must be timed serially, since under xdist every worker's wall clock overlaps.
Covering one new module is much cheaper than a full serial run — ``--store-durations`` merges
by default, so ``uv run pytest -n0 --store-durations tests/test_new.py`` adds that module's
timings and leaves the rest of the manifest alone.
"""

from __future__ import annotations

import json
from collections import Counter

import pytest

from tests.conftest import REPO_ROOT

DURATIONS_PATH = REPO_ROOT / ".test_durations"

# Ceiling on the share of collected tests carrying no recorded duration. Deliberately loose:
# a PR that adds a module shouldn't owe a full serial suite run before it can merge, and a
# mis-priced handful costs seconds. What this catches is the *slide* — #1772's 53%, and the
# corpus-parametrized files (`test_extracted_yaml_valid.py`) that grow with every extraction.
# At ~2,700 collected tests the gate trips around 270 unrecorded: several PRs' worth of drift,
# and well below the point where a shard can invert.
MAX_UNRECORDED_SHARE = 0.10

_REGEN = (
    "Regenerate with `mise run test:durations` "
    "(`uv run pytest -n0 --store-durations --clean-durations`)."
)
_REGEN_PARTIAL = (
    f"{_REGEN} Covering only the modules above is much cheaper and just as good: "
    "`uv run pytest -n0 --store-durations <module>...` merges into the existing manifest."
)


def test_durations_manifest_is_readable() -> None:
    """The manifest exists and is the ``{node id: seconds}`` map pytest-split expects."""
    assert DURATIONS_PATH.exists(), f"{DURATIONS_PATH.name} is missing. {_REGEN}"
    recorded = json.loads(DURATIONS_PATH.read_text(encoding="utf-8"))
    assert isinstance(recorded, dict) and recorded, f"{DURATIONS_PATH.name} is empty. {_REGEN}"
    assert all(isinstance(seconds, (int, float)) for seconds in recorded.values())


def test_durations_manifest_covers_the_collected_suite(
    collected_node_ids: list[str] | None,
) -> None:
    """At most ``MAX_UNRECORDED_SHARE`` of the collected suite may be unpriced.

    ``collected_node_ids`` (``conftest``) is the whole collection captured before pytest-split
    deselects the other shards — ``None`` when this run collected a subset, where the measure
    would be meaningless.
    """
    if collected_node_ids is None:
        pytest.skip("targeted run: duration coverage is only meaningful over the full suite")

    recorded = json.loads(DURATIONS_PATH.read_text(encoding="utf-8"))
    unrecorded = [nodeid for nodeid in collected_node_ids if nodeid not in recorded]
    share = len(unrecorded) / len(collected_node_ids)

    assert share <= MAX_UNRECORDED_SHARE, _report(len(collected_node_ids), unrecorded, share)


def _report(collected: int, unrecorded: list[str], share: float) -> str:
    """Name the uncovered modules — the fix is per-file, so a bare percentage isn't actionable."""
    by_module = Counter(nodeid.split("::", 1)[0] for nodeid in unrecorded)
    worst = "\n".join(f"  {count:>5}  {module}" for module, count in by_module.most_common(15))
    elided = len(by_module) - min(len(by_module), 15)
    tail = f"\n  ... and {elided} more module(s)" if elided else ""
    return (
        f"`.test_durations` is stale: {len(unrecorded)} of {collected} collected tests "
        f"({share:.0%}) have no recorded duration, over the {MAX_UNRECORDED_SHARE:.0%} ceiling. "
        f"pytest-split prices each of them at the average of the recorded ones, so the CI "
        f"shards are being balanced blind (#1772).\n\nUnrecorded tests by module:\n"
        f"{worst}{tail}\n\n{_REGEN_PARTIAL}"
    )
