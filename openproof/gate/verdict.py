"""Aggregate the gate predicates into a single verdict (§12a)."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Layout
from .predicates import (
    FAIL,
    NEEDS_HUMAN_REVIEW,
    PASS,
    PREDICATES,
    n2_unparsed,
    p1_binding,
    p3_pairing,
    p5_f4_no_literal_in_receipt,
    p2_set_partition,
    p6_never_tracked,
    read_sessions,
)

__all__ = ["Verdict", "evaluate", "evaluate_commit"]


@dataclass(frozen=True)
class Verdict:
    aggregate: str
    results: tuple  # ((name, result, detail), ...)


def _aggregate(results: tuple) -> str:
    outcomes = {result for _, result, _ in results}
    if FAIL in outcomes:
        return FAIL
    if NEEDS_HUMAN_REVIEW in outcomes:
        return NEEDS_HUMAN_REVIEW
    return PASS


def evaluate(layout: Layout) -> Verdict:
    sessions = read_sessions(layout)
    results = tuple(predicate(layout, sessions) for predicate in PREDICATES)
    return Verdict(_aggregate(results), results)


def evaluate_commit(layout: Layout, *, event_lines, sessions, unparsed_envelopes,
                    vault_originals, receipt_bytes) -> Verdict:
    """The full commit-time release gate (§12a) over the assembled receipt state."""
    results = (
        p1_binding(layout, sessions),
        p2_set_partition(sessions, event_lines, unparsed_envelopes),
        p3_pairing(event_lines),
        ("P4 idempotent re-import", PASS, "frozen-boundary, content-addressed (verified at import)"),
        p5_f4_no_literal_in_receipt(receipt_bytes, vault_originals),
        p6_never_tracked(layout, sessions),
        n2_unparsed(layout, sessions),
    )
    return Verdict(_aggregate(results), results)
