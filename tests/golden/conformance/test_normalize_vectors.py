"""Frozen golden vectors for the normalizer's content-block rule.

Locks the thinking-omission payload shape and the multi-block sub-anchor assignment, so a
future port reproduces the normalized event structure (which feeds the RawEvent id).
"""

from __future__ import annotations

from openproof.sources import claude_jsonl as cj

RECORD = {
    "type": "assistant",
    "uuid": "rec-uuid",
    "timestamp": "2026-06-07T00:00:00.000Z",
    "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "x", "signature": "sig"},
        {"type": "text", "text": "hello"},
        {"type": "tool_use", "id": "tu-1", "name": "Bash", "input": {"command": "ls"}},
    ]},
}


def test_thinking_payload_is_frozen():
    res = cj.normalize([RECORD], session_id="s")
    thinking = next(e for e in res.events if isinstance(e.payload, dict) and e.payload.get("blockType") == "thinking")
    assert thinking.payload == {
        "blockType": "thinking",
        "thinkingTextPresent": True,
        "thinkingTextCommitted": False,
        "opaqueSignaturePresent": True,
        "opaqueSignatureCommitted": False,
        "omittedFields": ["thinking", "signature"],
    }


def test_multi_block_sub_anchors_are_frozen():
    res = cj.normalize([RECORD], session_id="s")
    triples = sorted(
        (e.kind, e.native_anchor.primary, e.native_anchor.content_block_index) for e in res.events
    )
    assert triples == [
        ("assistant_msg", "rec-uuid", 0),  # thinking block at content index 0
        ("assistant_msg", "rec-uuid", 1),  # aggregated text, first text block at index 1
        ("tool_call", "tu-1", 2),          # tool_use anchored on its id, sub-anchor index 2
    ]


def test_text_aggregation_separator_is_frozen():
    rec = {"type": "assistant", "uuid": "u", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}
    res = cj.normalize([rec], session_id="s")
    assert res.events[0].payload == {"text": "a\nb"}  # newline-joined (locked spec-delegated detail)
