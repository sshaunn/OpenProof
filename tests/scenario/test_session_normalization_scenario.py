"""SCENARIO: §17 task-4 — normalize a real-shape Claude session end to end.

Mirrors the real corpus shapes (text/thinking/tool_use assistant blocks, tool_result
user records, known-noise, a compaction boundary). The story: no record is silently
dropped (the partition is a disjoint cover), recognized records each emit ≥1 event, the
thinking signature/text are never serialized, and compaction is surfaced as a ceiling.
"""

from __future__ import annotations

from openproof.sources import claude_jsonl as cj

TS = "2026-06-07T12:00:00.000Z"

SESSION = [
    {"type": "user", "uuid": "u1", "timestamp": TS, "message": {"role": "user", "content": "fix the bug"}},
    {"type": "file-history-snapshot", "uuid": "fh1"},  # known noise
    {"type": "assistant", "uuid": "a1", "timestamp": TS, "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "the user wants X", "signature": "OPAQUE_SIG_BYTES"},
        {"type": "text", "text": "I'll fix it."},
    ]}},
    {"type": "assistant", "uuid": "a2", "timestamp": TS, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "tu1", "name": "Edit", "input": {"file": "x.py"}},
    ]}},
    {"type": "user", "uuid": "u2", "timestamp": TS, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu1", "content": "edited", "is_error": False},
    ]}},
    {"type": "system", "subtype": "compact_boundary", "content": "earlier turns summarized", "uuid": "s1"},
    {"type": "attachment", "uuid": "att1"},  # known noise
]


def test_no_record_is_silently_dropped():
    res = cj.normalize(SESSION, session_id="sess")
    buckets = [res.parsed_indices, res.known_noise_indices, {u.record_index for u in res.unparsed_records}]
    assert set().union(*buckets) == set(range(len(SESSION)))  # disjoint cover (P2 shape)
    assert sum(len(b) for b in buckets) == len(SESSION)


def test_recognized_records_each_emit_at_least_one_event():
    res = cj.normalize(SESSION, session_id="sess")
    for index in res.parsed_indices:
        assert any(e.record_index == index for e in res.events)


def test_thinking_text_and_signature_never_serialized():
    res = cj.normalize(SESSION, session_id="sess")
    blob = repr([e.payload for e in res.events])
    assert "the user wants X" not in blob
    assert "OPAQUE_SIG_BYTES" not in blob
    # but the omission IS disclosed
    assert res.thinking_signature_omitted_count == 1
    thinking = next(e for e in res.events if isinstance(e.payload, dict) and e.payload.get("blockType") == "thinking")
    assert thinking.payload["thinkingTextPresent"] is True
    assert thinking.payload["opaqueSignaturePresent"] is True


def test_compaction_boundary_surfaced_as_ceiling():
    res = cj.normalize(SESSION, session_id="sess")
    assert res.compaction_boundary_count == 1
    # the boundary record is still routed to unparsed (a system subtype), never an event
    assert any(u.record_subtype == "compact_boundary" for u in res.unparsed_records)


def test_a_full_turn_is_citeable_and_paired():
    res = cj.normalize(SESSION, session_id="sess")
    kinds = {e.kind for e in res.events}
    assert {"prompt", "assistant_msg", "tool_call", "tool_result"} <= kinds
    call = next(e for e in res.events if e.kind == "tool_call")
    result = next(e for e in res.events if e.kind == "tool_result")
    assert call.pair_id == result.pair_id  # the result cites the call
