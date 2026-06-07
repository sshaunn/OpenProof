"""Unit tests for the §12a release-gate predicates + aggregate verdict."""

from __future__ import annotations

from openproof.canonical.encoding import canonical_bytes
from openproof.commands import init as init_cmd
from openproof.gate import evaluate
from openproof.gate.predicates import (
    DISCLOSURE,
    FAIL,
    NEEDS_HUMAN_REVIEW,
    PASS,
    n2_unparsed,
    p1_binding,
    p2_accounting,
    p6_never_tracked,
    read_sessions,
)


def _session(**kw):
    base = dict(
        source="claude_jsonl", sessionId="s1", sourceVersion="1", sourceRecordCount=3,
        parsedSourceRecordCount=1, eventCount=1, knownNoiseCount=1, knownNoiseCountsByType={},
        unparsedRecordCount=1, unparsedTypes=["system"], unparsedAcknowledgedTypes=[],
        compactionBoundaryCount=0, thinkingSignatureOmittedCount=0, redactionSummary={},
    )
    base.update(kw)
    return base


def _write_session(layout, session):
    layout.sessions.mkdir(parents=True, exist_ok=True)
    (layout.sessions / f"{session['source']}-{session['sessionId']}.yml").write_bytes(canonical_bytes(session) + b"\n")


def test_disclosure_is_frozen_and_never_says_safe():
    assert DISCLOSURE == (
        "Redacted: provider/cloud keys, private-key blocks, Bearer/JWT, connection-string "
        "passwords, and credential-keyword assignments. NOT guaranteed: rare, obfuscated, or "
        "non-standard secrets. Review the disclosure diff before confirming."
    )
    assert "safe" not in DISCLOSURE.lower()


def test_compaction_ceiling_is_the_verbatim_binding_sentence():
    from openproof.gate.predicates import compaction_ceiling

    assert compaction_ceiling(3) == (
        "This corpus contains 3 context-compaction boundary(ies); agent reasoning summarized "
        "away before each is not on disk and is unrecoverable by any OpenProof version — the "
        "transcript is complete only after the last boundary."
    )


def test_p1_binding_pass_and_fail(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert p1_binding(layout, [])[1] == PASS
    layout.config.unlink()  # no recorded fingerprint → unbound
    assert p1_binding(layout, [])[1] == FAIL


def test_p2_accounting_balance_and_break(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert p2_accounting(layout, [_session()])[1] == PASS  # 1+1+1 == 3
    assert p2_accounting(layout, [_session(sourceRecordCount=99)])[1] == FAIL  # arithmetic broken


def test_p6_never_tracked_pass_and_fail(fresh_repo, layout_of, run_git):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert p6_never_tracked(layout, [])[1] == PASS
    # force-track a raw payload path → P6 must FAIL
    raw = layout.raw / "claude_jsonl" / "s.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("payload", encoding="utf-8")
    run_git(["add", "-f", str(raw)], layout.repo_root)
    assert p6_never_tracked(layout, [])[1] == FAIL


def test_n2_unparsed_pass_and_needs_review(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert n2_unparsed(layout, [_session(unparsedRecordCount=0, unparsedTypes=[])])[1] == PASS
    assert n2_unparsed(layout, [_session()])[1] == NEEDS_HUMAN_REVIEW  # unacknowledged
    assert n2_unparsed(layout, [_session(unparsedAcknowledgedTypes=["system"])])[1] == PASS  # exact ack
    # a STRICT SUPERSET acknowledgment still PASSes (subset rule, not equality) and
    # a partial acknowledgment still NEEDS review
    assert n2_unparsed(layout, [_session(unparsedAcknowledgedTypes=["system", "mode"])])[1] == PASS
    assert n2_unparsed(layout, [_session(unparsedTypes=["system", "mode"], unparsedAcknowledgedTypes=["system"])])[1] == NEEDS_HUMAN_REVIEW


def test_read_sessions_empty_and_populated(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert read_sessions(layout) == []
    _write_session(layout, _session())
    assert len(read_sessions(layout)) == 1


def test_verdict_aggregates(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    assert evaluate(layout).aggregate == PASS  # clean, no sessions
    _write_session(layout, _session())  # unacknowledged unparsed → NEEDS_HUMAN_REVIEW
    assert evaluate(layout).aggregate == NEEDS_HUMAN_REVIEW
    _write_session(layout, _session(sessionId="s2", sourceRecordCount=99))  # break arithmetic → FAIL dominates
    assert evaluate(layout).aggregate == FAIL
