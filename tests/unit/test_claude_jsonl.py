"""Unit tests for the Claude JSONL normalizer (the content-block rule, routing)."""

from __future__ import annotations

from openproof.canonical.numbers import RawNumber
from openproof.sources import claude_jsonl as cj


def norm(records):
    return cj.normalize(records, session_id="s1")


def assistant(uuid, *blocks, ts="2026-06-07T00:00:00.000Z"):
    return {"type": "assistant", "uuid": uuid, "timestamp": ts, "message": {"role": "assistant", "content": list(blocks)}}


def text_block(t):
    return {"type": "text", "text": t}


def thinking_block(thinking="", signature=""):
    return {"type": "thinking", "thinking": thinking, "signature": signature}


def tool_use_block(id_, name="Bash", input_=None):
    return {"type": "tool_use", "id": id_, "name": name, "input": input_ or {}}


def user(uuid, content, ts="2026-06-07T00:00:00.000Z"):
    return {"type": "user", "uuid": uuid, "timestamp": ts, "message": {"role": "user", "content": content}}


def test_read_records_preserves_number_tokens_and_skips_blanks():
    text = '{"type":"user","n":9007199254740993}\n\n{"type":"assistant"}\n'
    records = cj.read_records(text)
    assert len(records) == 2
    assert isinstance(records[0]["n"], RawNumber)
    assert records[0]["n"].token == "9007199254740993"


def test_user_string_content_is_a_prompt():
    res = norm([user("u1", "hello there")])
    assert len(res.events) == 1
    assert res.events[0].kind == "prompt"
    assert res.events[0].payload == {"content": "hello there"}
    assert res.events[0].native_anchor.primary == "u1"


def test_assistant_text_blocks_aggregate_to_one_message():
    res = norm([assistant("a1", text_block("line one"), text_block("line two"))])
    assert len(res.events) == 1
    assert res.events[0].kind == "assistant_msg"
    assert res.events[0].payload == {"text": "line one\nline two"}


def test_tool_use_becomes_tool_call_keyed_by_id():
    res = norm([assistant("a1", tool_use_block("tu_1", "Read", {"path": "/x"}))])
    assert res.events[0].kind == "tool_call"
    assert res.events[0].native_anchor.primary == "tu_1"
    assert res.events[0].pair_id == "tu_1"
    assert res.events[0].payload == {"name": "Read", "input": {"path": "/x"}}


def test_thinking_block_emits_self_describing_omission_payload():
    res = norm([assistant("a1", thinking_block(thinking="deep thought", signature="sig123"))])
    assert len(res.events) == 1
    payload = res.events[0].payload
    assert payload["blockType"] == "thinking"
    assert payload["thinkingTextPresent"] is True
    assert payload["thinkingTextCommitted"] is False
    assert payload["opaqueSignaturePresent"] is True
    assert payload["omittedFields"] == ["thinking", "signature"]
    # neither the thinking text nor the signature is serialized
    assert "deep thought" not in str(payload) and "sig123" not in str(payload)


def test_empty_thinking_text_present_false():
    res = norm([assistant("a1", thinking_block(thinking="", signature="sig"))])
    payload = res.events[0].payload
    assert payload["thinkingTextPresent"] is False
    assert payload["omittedFields"] == ["signature"]


def test_thinking_signature_omitted_count():
    res = norm([assistant("a1", thinking_block(signature="s1")), assistant("a2", thinking_block(signature=""))])
    assert res.thinking_signature_omitted_count == 1  # only the non-empty signature counts


def test_multi_block_record_gets_content_block_sub_anchors():
    # a thinking block AND a text block (both assistant_msg) must not collide on anchor
    res = norm([assistant("a1", thinking_block(signature="s"), text_block("hi"))])
    assert len(res.events) == 2
    anchors = {(e.native_anchor.primary, e.native_anchor.content_block_index) for e in res.events}
    assert anchors == {("a1", 0), ("a1", 1)}  # distinct sub-anchors


def test_single_event_record_has_no_sub_anchor():
    res = norm([assistant("a1", text_block("hi"))])
    assert res.events[0].native_anchor.content_block_index is None


def test_empty_assistant_record_still_emits_one_event():
    res = norm([assistant("a1")])
    assert len(res.events) == 1 and res.events[0].kind == "assistant_msg"


def test_user_tool_result_is_paired():
    rec = user("u1", [{"type": "tool_result", "tool_use_id": "tu_1", "content": "ok", "is_error": False}])
    res = norm([rec])
    event = res.events[0]
    assert event.kind == "tool_result"
    assert event.pair_id == "tu_1"  # tool_use_id is the PAIR key …
    assert event.native_anchor.primary == "u1"  # … the record UUID is the ANCHOR primary (§6 item 2)
    assert event.native_anchor.content_block_index is None  # single event → no sub-anchor
    assert event.payload == {"content": "ok", "isError": False}


def test_tool_result_is_error_true_propagates():
    rec = user("u1", [{"type": "tool_result", "tool_use_id": "tu_1", "content": "boom", "is_error": True}])
    res = norm([rec])
    assert res.events[0].payload == {"content": "boom", "isError": True}


def test_multiple_tool_results_get_sub_anchors():
    rec = user("u1", [
        {"type": "tool_result", "tool_use_id": "t1", "content": "a"},
        {"type": "tool_result", "tool_use_id": "t2", "content": "b"},
    ])
    res = norm([rec])
    assert {e.native_anchor.content_block_index for e in res.events} == {0, 1}
    assert all(e.native_anchor.primary == "u1" for e in res.events)  # anchor = record UUID
    assert {e.pair_id for e in res.events} == {"t1", "t2"}  # each keeps its own pair key


def test_event_carries_source_session_and_native_ts():
    res = cj.normalize([user("u1", "hi", ts="2026-06-07T09:30:00.000Z")], session_id="sess-X")
    event = res.events[0]
    assert event.source == "claude_jsonl"
    assert event.session_id == "sess-X"
    assert event.ts == "2026-06-07T09:30:00.000Z"  # §8: the native event timestamp is preserved


def test_non_compact_boundary_system_record_not_counted():
    # only subtype compact_boundary counts; a local_command system record must NOT (§6 item 2)
    res = norm([{"type": "system", "subtype": "local_command", "content": "x"}])
    assert res.compaction_boundary_count == 0
    assert len(res.unparsed_records) == 1  # still routed to unparsed


def test_user_text_blocks_become_prompt():
    res = norm([user("u1", [text_block("part a"), text_block("part b")])])
    assert res.events[0].kind == "prompt"
    assert res.events[0].payload == {"content": "part a\npart b"}


def test_known_noise_filtered_not_evented():
    records = [{"type": t, "uuid": f"n{i}"} for i, t in enumerate(sorted(cj.KNOWN_NOISE_TYPES))]
    res = norm(records)
    assert res.events == ()
    assert res.known_noise_indices == frozenset(range(len(records)))


def test_unknown_types_routed_to_unparsed():
    res = norm([{"type": "system", "subtype": "local_command", "content": "x"}, {"type": "mode"}])
    assert {u.record_index for u in res.unparsed_records} == {0, 1}
    assert res.events == ()


def test_compact_boundary_counted_but_still_unparsed():
    res = norm([{"type": "system", "subtype": "compact_boundary", "content": "summary"}])
    assert res.compaction_boundary_count == 1
    assert len(res.unparsed_records) == 1  # still routed to unparsed (a system subtype)


def test_partition_is_a_disjoint_cover():
    records = [user("u1", "hi"), {"type": "attachment"}, {"type": "system", "subtype": "x"}]
    res = norm(records)
    buckets = res.parsed_indices, res.known_noise_indices, {u.record_index for u in res.unparsed_records}
    assert set().union(*buckets) == {0, 1, 2}
    assert sum(len(b) for b in buckets) == 3  # pairwise disjoint
