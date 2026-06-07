"""SCENARIO: a developer promotes the ledger into Git with `openproof commit` (§7 step 5).

The only promotion path: re-run the gate, write a candidate to staging, confirm, and
transactionally promote an immutable content-addressed receipt. Asserts the safety story —
nothing trackable leaks, the receipt is deterministic + immutable, and the gate blocks.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from openproof.commands import commit as commit_cmd
from openproof.commands import import_claude
from openproof.commands import init as init_cmd
from openproof.errors import GateBlockedError, ReceiptCorruptionError

TS = "2026-06-07T10:00:0"


def _setup(fresh_repo, layout_of, tmp_path, records, session_id="sess1"):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    projects = tmp_path / "projects" / "slug"
    projects.mkdir(parents=True)
    for record in records:
        record.setdefault("cwd", str(layout.repo_root))
    (projects / f"{session_id}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    import_claude.run(fresh_repo, out=lambda *a: None, projects_dir=tmp_path / "projects")
    return layout


def _clean_session(secret="export TUSHARE_TOKEN=xyz"):
    return [
        {"type": "user", "uuid": "u1", "sessionId": "sess1", "timestamp": TS + "0.000Z",
         "message": {"role": "user", "content": "go"}},
        {"type": "assistant", "uuid": "a1", "timestamp": TS + "1.000Z",
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": secret}}]}},
        {"type": "user", "uuid": "u2", "timestamp": TS + "2.000Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "ok", "is_error": False}]}},
    ]


def _ls(layout, *paths):
    out = subprocess.run(["git", "ls-files", *paths], cwd=str(layout.repo_root), capture_output=True, text=True).stdout
    return [p for p in out.splitlines() if p.strip()]


def test_commit_promotes_an_immutable_tracked_receipt(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())
    lines = []
    assert commit_cmd.run(fresh_repo, out=lines.append, confirm=lambda: True) == 0
    assert any("COMMITTED" in line for line in lines)

    committed = list(layout.committed.glob("*"))
    assert len(committed) == 1
    assert {p.name for p in committed[0].iterdir()} == {"events.jsonl", "unparsed.jsonl", "manifest.yml"}
    # only committed/ is the tracked transcript surface; raw/vault/staging never tracked (P6/F4)
    assert _ls(layout, ".openproof/committed")  # tracked
    assert _ls(layout, ".openproof/raw", ".openproof/vault", ".openproof/staging") == []


def test_committed_receipt_holds_no_secret(fresh_repo, layout_of, tmp_path):
    secret = "supersecretvalue99"
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session(secret="export API_TOKEN=" + secret))
    commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True)
    receipt = b"".join((list(layout.committed.glob("*"))[0] / f).read_bytes()
                       for f in ("events.jsonl", "unparsed.jsonl", "manifest.yml"))
    assert secret.encode() not in receipt
    assert str(layout.repo_root).encode() not in receipt  # no absolute path either


def test_decline_leaves_nothing_committed(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())
    lines = []
    assert commit_cmd.run(fresh_repo, out=lines.append, confirm=lambda: False) == 0
    assert any("Declined" in line for line in lines)
    assert list(layout.committed.glob("*")) == []  # no receipt created
    assert list(layout.staging.glob("*")) == []     # staging swept
    assert _ls(layout, ".openproof/raw", ".openproof/vault", ".openproof/staging") == []


def test_recommit_is_idempotent_and_byte_identical(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())
    commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True)
    receipt_dir = list(layout.committed.glob("*"))[0]
    before = (receipt_dir / "manifest.yml").read_bytes()
    lines = []
    commit_cmd.run(fresh_repo, out=lines.append, confirm=lambda: True)  # same ledger → same hash
    assert any("DUPLICATE" in line for line in lines)
    assert (receipt_dir / "manifest.yml").read_bytes() == before  # never rewritten
    assert len(list(layout.committed.glob("*"))) == 1


def test_f5_aborts_on_a_tampered_receipt(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())
    commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True)
    (list(layout.committed.glob("*"))[0] / "manifest.yml").write_bytes(b'{"tampered":true}\n')
    with pytest.raises(ReceiptCorruptionError):
        commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True)


def test_git_only_evidence_commit(committed_repo, layout_of):
    # a repo with git history but NO imported transcript → GIT_ONLY_EVIDENCE receipt
    init_cmd.run(committed_repo, out=lambda *a: None)
    layout = layout_of(committed_repo)
    lines = []
    assert commit_cmd.run(committed_repo, out=lines.append, confirm=lambda: True) == 0
    assert any("git evidence only" in line for line in lines)
    manifest = json.loads((list(layout.committed.glob("*"))[0] / "manifest.yml").read_bytes())
    assert manifest["mode"] == "GIT_ONLY_EVIDENCE"
    boundary = manifest["evidenceBoundary"]
    # §12a git-only boundary: headSha + branch + working-tree file names (never empty/vacuous)
    assert boundary["headSha"] and boundary["branch"]
    assert isinstance(boundary["workingTreeFiles"], list)


def test_gate_blocks_unacknowledged_unparsed(fresh_repo, layout_of, tmp_path):
    records = _clean_session() + [{"type": "system", "subtype": "compact_boundary", "content": "x", "uuid": "s1"}]
    _setup(fresh_repo, layout_of, tmp_path, records)
    with pytest.raises(GateBlockedError):
        commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True)  # no --ack-unparsed → N2 blocks
    # with the acknowledgment, it promotes
    assert commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True, ack_unparsed=True) == 0


def test_commit_outside_git_is_unbound(tmp_path):
    from openproof.errors import UnboundRepoError

    with pytest.raises(UnboundRepoError):
        commit_cmd.run(tmp_path, out=lambda *a: None, confirm=lambda: True)


def test_interrupt_at_prompt_removes_staging(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())

    def interrupt():
        raise KeyboardInterrupt

    lines = []
    assert commit_cmd.run(fresh_repo, out=lines.append, confirm=interrupt) == 0  # SIGINT at the prompt
    assert any("Interrupted" in line for line in lines)
    assert list(layout.committed.glob("*")) == []  # nothing committed
    assert list(layout.staging.glob("*")) == []     # staging removed


def test_ack_unparsed_persists_audit_fields_but_not_in_receipt(fresh_repo, layout_of, tmp_path):
    records = _clean_session() + [{"type": "system", "subtype": "compact_boundary", "content": "x", "uuid": "s1"}]
    layout = _setup(fresh_repo, layout_of, tmp_path, records)
    commit_cmd.run(fresh_repo, out=lambda *a: None, confirm=lambda: True, ack_unparsed=True)
    summary = json.loads(next(layout.sessions.glob("*.yml")).read_bytes())
    assert "unparsedAcknowledgedBy" in summary and "unparsedAcknowledgedAt" in summary  # local audit
    # the WHO/WHEN are §12c EXCLUDE fields — they must NOT appear in the receipt
    manifest = (list(layout.committed.glob("*"))[0] / "manifest.yml").read_bytes()
    assert b"unparsedAcknowledgedBy" not in manifest and b"unparsedAcknowledgedAt" not in manifest


def test_commit_reconciles_leftover_staging_on_startup(fresh_repo, layout_of, tmp_path):
    layout = _setup(fresh_repo, layout_of, tmp_path, _clean_session())
    (layout.staging / "deadbeefstale").mkdir(parents=True)  # residue of an uncatchable termination
    lines = []
    commit_cmd.run(fresh_repo, out=lines.append, confirm=lambda: True)
    assert any("reconcile" in line and "staging" in line for line in lines)
    assert not (layout.staging / "deadbeefstale").exists()
