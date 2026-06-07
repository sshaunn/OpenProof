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


# --- commit-time predicates (need the committed event/unparsed/vault state) ---

def p2_set_partition(sessions, event_lines, unparsed_envelopes):
    """The receipt-only §12a P2: per-session, the distinct parsed indices (event rawOffsets)
    and unparsed indices are disjoint, in range, and match the committed counts (F1)."""
    parsed, unparsed = {}, {}
    for line in event_lines:
        key = (line["source"], line["sessionId"])
        for index in line["rawOffsets"]:
            parsed.setdefault(key, set()).add(index)
    for env in unparsed_envelopes:
        key = (env["source"], env["sessionId"])
        bucket = unparsed.setdefault(key, set())
        if env["recordIndex"] in bucket:
            return ("P2 no record silently dropped", FAIL, f"duplicate unparsed index in {key}")
        bucket.add(env["recordIndex"])
    for summary in sessions:
        key = (summary["source"], summary["sessionId"])
        p, u, n = parsed.get(key, set()), unparsed.get(key, set()), summary["sourceRecordCount"]
        if p & u:
            return ("P2 no record silently dropped", FAIL, f"parsed/unparsed index overlap in {key}")
        if any(not (0 <= i < n) for i in p | u):
            return ("P2 no record silently dropped", FAIL, f"index out of range in {key}")
        if len(p) != summary["parsedSourceRecordCount"] or len(u) != summary["unparsedRecordCount"]:
            return ("P2 no record silently dropped", FAIL, f"index count disagrees with summary in {key}")
        if summary["parsedSourceRecordCount"] + summary["knownNoiseCount"] + summary["unparsedRecordCount"] != n:
            return ("P2 no record silently dropped", FAIL, f"partition arithmetic broken for {key}")
    return ("P2 no record silently dropped", PASS, "per-session set-partition well-formed")


def _source_pos(line):
    """A source-order key for an event: (sessionId, earliest source record index)."""
    return (line.get("sessionId"), min(line["rawOffsets"]) if line.get("rawOffsets") else 0)


def p3_pairing(event_lines):
    """§12a P3: every tool_use has a paired tool_result, or the single unpaired one is the
    single TRAILING in-progress tail; an interior unpaired tool_use → F2 FAIL."""
    results = {line.get("pairId") for line in event_lines if line["kind"] == "tool_result"}
    unpaired = [line for line in event_lines if line["kind"] == "tool_call" and line.get("pairId") not in results]
    if len(unpaired) > 1:
        return ("P3 pairing complete", FAIL, f"{len(unpaired)} interior unpaired tool_use")
    if unpaired:
        tail = unpaired[0]
        later = [l for l in event_lines if l.get("sessionId") == tail.get("sessionId") and _source_pos(l) > _source_pos(tail)]
        if later:  # something follows it in-session → it is interior, not the trailing tail
            return ("P3 pairing complete", FAIL, "interior unpaired tool_use (not the trailing tail)")
    return ("P3 pairing complete", PASS, "tool_use/tool_result paired" + (" (one trailing tail)" if unpaired else ""))


def p5_f4_no_literal_in_receipt(receipt_bytes, vault_originals):
    """§12a P5/F4 self-test: zero matched secret literal survives anywhere in the receipt."""
    text = receipt_bytes.decode("utf-8", "replace")
    survivors = [o for o in vault_originals if o and o in text]
    if survivors:
        return ("P5/F4 no matched literal in receipt", FAIL,
                f"a matched secret literal survives in the receipt ({len(survivors)} field(s))")
    return ("P5/F4 no matched literal in receipt", PASS, "zero matched literal in events/unparsed/manifest")
