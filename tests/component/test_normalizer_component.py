"""Component tests: normalize a realistic multi-record Claude session."""

from __future__ import annotations

from openproof.sources import claude_jsonl as cj

TS = "2026-06-07T12:00:00.000Z"


def _session():
    return [
        {"type": "user", "uuid": "u1", "timestamp": TS, "message": {"role": "user", "content": "run the tests"}},
        {"type": "queue-operation", "uuid": "q1"},  # known noise
        {"type": "assistant", "uuid": "a1", "timestamp": TS, "message": {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": "Running tests now."},
            {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "pytest"}},
        ]}},
        {"type": "user", "uuid": "u2", "timestamp": TS, "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": "142 passed", "is_error": False},
        ]}},
        {"type": "system", "subtype": "compact_boundary", "content": "summary", "uuid": "s1"},
    ]


def test_session_partition_and_counts():
    res = cj.normalize(_session(), session_id="s1")
    assert len(res.parsed_indices) == 3  # u1, a1, u2
    assert res.known_noise_indices == frozenset({1})
    assert {u.record_index for u in res.unparsed_records} == {4}
    # the assistant record block-expands to 3 events → eventCount >= parsedCount
    assert len(res.events) >= len(res.parsed_indices)
    assert res.compaction_boundary_count == 1
    assert res.thinking_signature_omitted_count == 1


def test_assistant_record_yields_three_distinct_events():
    res = cj.normalize(_session(), session_id="s1")
    a1 = [e for e in res.events if e.record_index == 2]
    assert {e.kind for e in a1} == {"assistant_msg", "tool_call"}  # thinking+text both assistant_msg
    # all three share the record uuid as primary but have distinct content_block_index
    assert len(a1) == 3
    assert len({e.native_anchor.content_block_index for e in a1}) == 3


def test_tool_call_and_result_share_pair_id():
    res = cj.normalize(_session(), session_id="s1")
    call = next(e for e in res.events if e.kind == "tool_call")
    result = next(e for e in res.events if e.kind == "tool_result")
    assert call.pair_id == result.pair_id == "tu1"


def test_normalize_is_deterministic():
    a = cj.normalize(_session(), session_id="s1")
    b = cj.normalize(_session(), session_id="s1")
    assert [(e.kind, e.native_anchor.primary, e.native_anchor.content_block_index) for e in a.events] == \
           [(e.kind, e.native_anchor.primary, e.native_anchor.content_block_index) for e in b.events]
