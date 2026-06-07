"""Unit tests for the commit-time gate predicates (§12a P2 set-partition, P3, P5/F4)."""

from __future__ import annotations

from openproof.commands import init as init_cmd
from openproof.gate import evaluate_commit
from openproof.gate.predicates import FAIL, PASS, p2_set_partition, p3_pairing, p5_f4_no_literal_in_receipt


def _session(**kw):
    base = dict(source="claude_jsonl", sessionId="s", sourceRecordCount=3,
                parsedSourceRecordCount=2, knownNoiseCount=0, unparsedRecordCount=1)
    base.update(kw)
    return base


def _event(idx, source="claude_jsonl", session="s", kind="prompt", pair=None):
    return {"source": source, "sessionId": session, "kind": kind, "rawOffsets": [idx], "pairId": pair}


def _envelope(idx, source="claude_jsonl", session="s"):
    return {"source": source, "sessionId": session, "recordIndex": idx}


def test_p2_set_partition_pass():
    sessions = [_session()]
    events = [_event(0), _event(1)]
    unparsed = [_envelope(2)]
    assert p2_set_partition(sessions, events, unparsed)[1] == PASS


def test_p2_fails_on_duplicate_unparsed_index():
    assert p2_set_partition([_session(unparsedRecordCount=2)], [_event(0), _event(1)], [_envelope(2), _envelope(2)])[1] == FAIL


def test_p2_fails_on_parsed_unparsed_overlap():
    assert p2_set_partition([_session()], [_event(0), _event(1)], [_envelope(1)])[1] == FAIL


def test_p2_fails_on_out_of_range_index():
    assert p2_set_partition([_session()], [_event(0), _event(9)], [_envelope(2)])[1] == FAIL


def test_p2_fails_on_count_mismatch():
    assert p2_set_partition([_session(sourceRecordCount=99)], [_event(0), _event(1)], [_envelope(2)])[1] == FAIL


def test_p2_fails_when_index_count_disagrees_with_summary():
    # 1 distinct parsed index but the summary claims parsedSourceRecordCount=2 (arithmetic still balances)
    assert p2_set_partition([_session(parsedSourceRecordCount=2)], [_event(0)], [_envelope(2)])[1] == FAIL


def test_p3_pairing_paired():
    events = [_event(0, kind="tool_call", pair="t1"), _event(1, kind="tool_result", pair="t1")]
    assert p3_pairing(events)[1] == PASS


def test_p3_allows_single_trailing_tail():
    events = [_event(0, kind="tool_call", pair="t1")]  # one unpaired = the in-progress tail
    assert p3_pairing(events)[1] == PASS


def test_p3_fails_on_interior_unpaired():
    events = [_event(0, kind="tool_call", pair="t1"), _event(1, kind="tool_call", pair="t2")]
    assert p3_pairing(events)[1] == FAIL  # two unpaired → interior


def test_p3_fails_on_single_interior_unpaired():
    # one unpaired tool_use, but a later event follows it in-session → interior, not trailing
    events = [_event(0, kind="tool_call", pair="t1"), _event(1, kind="prompt")]
    assert p3_pairing(events)[1] == FAIL


def test_evaluate_commit_pass_and_f4_fail(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    sessions = [_session(sourceRecordCount=1, parsedSourceRecordCount=1, knownNoiseCount=0, unparsedRecordCount=0)]
    events = [_event(0, kind="prompt")]
    common = dict(event_lines=events, sessions=sessions, unparsed_envelopes=[], vault_originals=["livesecret"])
    assert evaluate_commit(layout, receipt_bytes=b'{"redacted":"<REDACTED:credential_keyword#0>"}', **common).aggregate == PASS
    # a vault secret surviving in the receipt → P5/F4 FAIL → the gate (and commit) aborts
    assert evaluate_commit(layout, receipt_bytes=b'{"leak":"livesecret"}', **common).aggregate == FAIL


def test_p5_f4_pass_and_fail():
    assert p5_f4_no_literal_in_receipt(b'{"payload":"<REDACTED:credential_keyword#0>"}', ["livesecret"])[1] == PASS
    assert p5_f4_no_literal_in_receipt(b'{"payload":"oops livesecret here"}', ["livesecret"])[1] == FAIL
