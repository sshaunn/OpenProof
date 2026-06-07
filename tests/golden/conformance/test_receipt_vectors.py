"""Frozen golden vector for the §12c ledgerStateHash over a fixed minimal ledger."""

from __future__ import annotations

from openproof.commit.snapshot import CLAUDE_LEDGER, build_snapshot

GOLDEN_LEDGER_STATE_HASH = "5a1f63cbc461c43b9b37e867e0b87ab806c3b7af73a33e2cd4529f405502fdd0"

EVENT_LINE = {
    "id": "id1", "kind": "prompt", "source": "claude_jsonl", "sessionId": "s",
    "ts": "2026-06-07T10:00:00.000Z", "payload": {"content": "hi"}, "rawOffsets": [0],
    "nativeAnchor": {"primary": "u1"}, "redactionMarkers": [], "schemaVersion": 1, "trust": "HIGH",
}


def _snapshot():
    return build_snapshot(
        schema_version=1, spec_version="0.1.0",
        repo_fingerprint={"status": "unavailable", "reason": "historyless"}, mode=CLAUDE_LEDGER,
        event_lines=[EVENT_LINE], sessions=[], unparsed_by_session={},
        git_changesets=[], git_facts={}, redaction_summary={}, gate_results=[],
    )


def test_golden_ledger_state_hash():
    assert _snapshot().ledger_state_hash == GOLDEN_LEDGER_STATE_HASH


def test_receipt_is_deterministic_across_runs():
    a, b = _snapshot(), _snapshot()
    assert a.ledger_state_hash == b.ledger_state_hash
    assert a.events_bytes == b.events_bytes
    assert a.manifest_bytes == b.manifest_bytes


def test_repo_fingerprint_in_every_event_line_byte_identical_with_manifest():
    # §12c item 5 / §17 task 10: the repositoryIdentity object appears in BOTH the manifest
    # and every events.jsonl line, byte-identical (no path-derived value anywhere)
    snap = _snapshot()
    fingerprint = b'"repoFingerprint":{"reason":"historyless","status":"unavailable"}'
    assert fingerprint in snap.events_bytes
    assert fingerprint in snap.manifest_bytes
