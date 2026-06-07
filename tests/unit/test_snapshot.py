"""Unit tests for the receipt builders (§12c): eventRecordHash, unparsed envelope, hash."""

from __future__ import annotations

from openproof.canonical.hashing import domain_hash
from openproof.commit.snapshot import (
    CLAUDE_LEDGER,
    build_snapshot,
    build_unparsed_envelope,
    event_record_hash,
)

EVENT_LINE = {"id": "id1", "kind": "prompt", "source": "claude_jsonl", "sessionId": "s",
              "ts": "2026-06-07T10:00:00.000Z", "payload": {"content": "hi"}, "rawOffsets": [0]}


def test_event_record_hash_is_domain_separated():
    h = event_record_hash(EVENT_LINE)
    assert h == domain_hash("event-record", {"core": EVENT_LINE})
    # a distinct domain → distinct hash on the same input (no cross-kind collision)
    assert h != domain_hash("rawevent-id", {"core": EVENT_LINE})


def test_unparsed_envelope_shape_and_non_circularity():
    unparsed = {"recordIndex": 3, "recordType": "system", "recordSubtype": "compact_boundary",
                "raw": {"type": "system", "subtype": "compact_boundary", "content": "x", "cwd": "/abs/secret"}}
    envelope, triple, _vault = build_unparsed_envelope(unparsed, "claude_jsonl", "s", 1)
    # the absolute path is never carried into the envelope
    assert "/abs/secret" not in str(envelope)
    # redactedRecordHash is NOT a function of its own output (carved-out core)
    core = {k: envelope[k] for k in envelope if k not in ("redactedRecordHash", "opaqueId")}
    assert envelope["redactedRecordHash"] == domain_hash("redacted-record", {"core": core})
    assert triple["opaqueId"] == envelope["opaqueId"]


def test_snapshot_determinism_and_no_oracle():
    def snap(secret_line):
        events = [dict(EVENT_LINE, id="e", payload={"text": secret_line}, ts="2026-06-07T10:00:00.000Z")]
        return build_snapshot(
            schema_version=1, spec_version="0.1.0", repo_fingerprint={"status": "unavailable", "reason": "historyless"},
            mode=CLAUDE_LEDGER, event_lines=events, sessions=[], unparsed_by_session={},
            git_changesets=[], git_facts={}, redaction_summary={}, gate_results=[],
        )
    a, a2 = snap("<REDACTED:credential_keyword#0>"), snap("<REDACTED:credential_keyword#0>")
    assert a.ledger_state_hash == a2.ledger_state_hash
    assert a.events_bytes == a2.events_bytes and a.manifest_bytes == a2.manifest_bytes


def test_session_window_binding():
    def snap(ts):
        events = [dict(EVENT_LINE, id="e", ts=ts)]
        return build_snapshot(
            schema_version=1, spec_version="0.1.0", repo_fingerprint={"status": "unavailable", "reason": "historyless"},
            mode=CLAUDE_LEDGER, event_lines=events, sessions=[], unparsed_by_session={},
            git_changesets=[], git_facts={}, redaction_summary={}, gate_results=[],
        )
    # two ledgers differing ONLY in an event ts must produce a different ledgerStateHash
    assert snap("2026-06-07T10:00:00.000Z").ledger_state_hash != snap("2026-06-07T11:00:00.000Z").ledger_state_hash


def test_session_window_spans_first_to_last():
    import json

    events = [dict(EVENT_LINE, id="e1", ts="2026-06-07T10:00:00.000Z"),
              dict(EVENT_LINE, id="e2", ts="2026-06-07T12:30:00.000Z")]
    snap = build_snapshot(
        schema_version=1, spec_version="0.1.0", repo_fingerprint={"status": "unavailable", "reason": "historyless"},
        mode=CLAUDE_LEDGER, event_lines=events, sessions=[], unparsed_by_session={},
        git_changesets=[], git_facts={}, redaction_summary={}, gate_results=[],
    )
    window = json.loads(snap.manifest_bytes)["evidenceBoundary"]["sessionWindow"]
    assert window["firstNativeEventTs"] == "2026-06-07T10:00:00.000Z"
    assert window["lastNativeEventTs"] == "2026-06-07T12:30:00.000Z"  # last ≠ first across the span
