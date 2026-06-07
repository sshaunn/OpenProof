"""The claude_jsonl source satisfies the Source seam (the extensibility contract)."""

from __future__ import annotations

from openproof.sources import base, claude_jsonl


def test_claude_jsonl_conforms_to_the_source_interface():
    # the seam a future Codex/manual adapter must also satisfy
    assert hasattr(base, "Source")
    assert claude_jsonl.name == "claude_jsonl"
    assert callable(claude_jsonl.read_records)
    assert callable(claude_jsonl.normalize)


def test_round_trip_read_then_normalize():
    text = '{"type":"user","uuid":"u1","message":{"role":"user","content":"hi"}}'
    records = claude_jsonl.read_records(text)
    result = claude_jsonl.normalize(records, session_id="s")
    assert result.events[0].kind == "prompt"
