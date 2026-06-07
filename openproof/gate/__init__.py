"""The release acceptance gate — pure predicates over the ledger state (§12a).

Build-step-5 ships the predicates `status`/`doctor` need (P1 binding, the P2 count
accounting, P6 never-tracked, N2 unparsed) + the aggregate verdict + the frozen
disclosure. The full commit-time gate (the local set-partition, P3–P5, F1–F5) and
`ledgerStateHash` arrive with `commit` in build-step-6.
"""

from __future__ import annotations

from .predicates import DISCLOSURE, FAIL, NEEDS_HUMAN_REVIEW, PASS
from .verdict import Verdict, evaluate

__all__ = ["DISCLOSURE", "PASS", "FAIL", "NEEDS_HUMAN_REVIEW", "Verdict", "evaluate"]
