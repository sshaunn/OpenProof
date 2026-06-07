"""Aggregate the gate predicates into a single verdict (§12a)."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Layout
from .predicates import FAIL, NEEDS_HUMAN_REVIEW, PASS, PREDICATES, read_sessions

__all__ = ["Verdict", "evaluate"]


@dataclass(frozen=True)
class Verdict:
    aggregate: str
    results: tuple  # ((name, result, detail), ...)


def evaluate(layout: Layout) -> Verdict:
    sessions = read_sessions(layout)
    results = tuple(predicate(layout, sessions) for predicate in PREDICATES)
    outcomes = {result for _, result, _ in results}
    if FAIL in outcomes:
        aggregate = FAIL
    elif NEEDS_HUMAN_REVIEW in outcomes:
        aggregate = NEEDS_HUMAN_REVIEW
    else:
        aggregate = PASS
    return Verdict(aggregate, results)
