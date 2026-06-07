"""Release-gate predicates as pure functions over the imported ledger state (§12a).

Each predicate takes ``(layout, sessions)`` and returns ``(name, result, detail)`` where
``result ∈ {PASS, FAIL, NEEDS_HUMAN_REVIEW}``. ``sessions`` is the list of committed
``ImportedSession`` summaries (the receipt-only view), so these predicates are exactly the
ones a second party can recompute from on-disk facts.
"""

from __future__ import annotations

import json

from ..config import Layout
from ..git import repo as gitrepo

__all__ = ["DISCLOSURE", "GIT_ONLY_DISCLOSURE", "compaction_ceiling", "PASS", "FAIL",
           "NEEDS_HUMAN_REVIEW", "read_sessions", "PREDICATES"]

PASS, FAIL, NEEDS_HUMAN_REVIEW = "PASS", "FAIL", "NEEDS_HUMAN_REVIEW"

# §12a binding disclosure-message rule — the word "safe" never appears unqualified.
DISCLOSURE = (
    "Redacted: provider/cloud keys, private-key blocks, Bearer/JWT, connection-string "
    "passwords, and credential-keyword assignments. NOT guaranteed: rare, obfuscated, or "
    "non-standard secrets. Review the disclosure diff before confirming."
)
GIT_ONLY_DISCLOSURE = "No transcript records were imported; this receipt contains git evidence only."


def compaction_ceiling(n: int) -> str:
    """The §12a binding context-compaction-ceiling sentence (verbatim), reused by commit."""
    return (
        f"This corpus contains {n} context-compaction boundary(ies); agent reasoning "
        "summarized away before each is not on disk and is unrecoverable by any OpenProof "
        "version — the transcript is complete only after the last boundary."
    )

NEVER_TRACKED = [".openproof/raw", ".openproof/vault", ".openproof/staging"]


def read_sessions(layout: Layout) -> list:
    if not layout.sessions.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(layout.sessions.glob("*.yml"))]


def p1_binding(layout: Layout, sessions: list):
    bound = layout.config.exists() and gitrepo.is_git_repo(layout.repo_root)
    return ("P1 binding resolved", PASS if bound else FAIL,
            "repo bound + fingerprint recorded" if bound else "unbound")


def p2_accounting(layout: Layout, sessions: list):
    # the receipt-only P2: the per-session count partition is recomputable from the summary
    # (parsed + known-noise + unparsed == sourceRecordCount). The full index set-partition is
    # the LOCAL commit-time gate (build-step-6). Per the 2026-06-07 amendment, P2 is the
    # set-partition, NOT the eventCount>=parsedSourceRecordCount bound (dup records dedupe).
    for s in sessions:
        if s["parsedSourceRecordCount"] + s["knownNoiseCount"] + s["unparsedRecordCount"] != s["sourceRecordCount"]:
            return ("P2 no record silently dropped", FAIL, f"partition arithmetic broken for {s['sessionId']}")
    return ("P2 no record silently dropped", PASS, f"{len(sessions)} session(s) balance")


def p6_never_tracked(layout: Layout, sessions: list):
    tracked = gitrepo.tracked_under(layout.repo_root, *NEVER_TRACKED)
    return ("P6 transcript payload never tracked", PASS if not tracked else FAIL,
            "raw/ vault/ staging/ untracked" if not tracked else f"TRACKED payload: {tracked}")


def n2_unparsed(layout: Layout, sessions: list):
    flagged = [
        s["sessionId"] for s in sessions
        if s["unparsedRecordCount"] > 0
        and not set(s.get("unparsedTypes", [])) <= set(s.get("unparsedAcknowledgedTypes", []))
    ]
    if flagged:
        return ("N2 unrecognized record types", NEEDS_HUMAN_REVIEW,
                f"unacknowledged unparsed types in {flagged} — run `commit --ack-unparsed`")
    return ("N2 unrecognized record types", PASS, "no unacknowledged unparsed types")


PREDICATES = (p1_binding, p2_accounting, p6_never_tracked, n2_unparsed)
