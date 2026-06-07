"""SCENARIO: a developer inspects the ledger with `status` and `doctor` (§7 step 4).

After init → import, `status` shows the binding, per-session counts, the release-gate
result and the qualified disclosure; `doctor` re-asserts the safety invariants. The story
covers the human-readable surface a developer relies on before deciding to commit.
"""

from __future__ import annotations

import json

from openproof.commands import doctor as doctor_cmd
from openproof.commands import import_claude
from openproof.commands import init as init_cmd
from openproof.commands import status as status_cmd


def _run(fn, *a, **kw):
    out = []
    rc = fn(*a, out=out.append, **kw)
    return rc, "\n".join(out)


def test_init_import_status_doctor_flow(fresh_repo, layout_of, tmp_path):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    repo_root = layout_of(fresh_repo).repo_root
    projects = tmp_path / "projects" / "slug"
    projects.mkdir(parents=True)
    records = [
        {"type": "user", "uuid": "u1", "cwd": str(repo_root), "sessionId": "sess-S",
         "message": {"role": "user", "content": "deploy"}},
        {"type": "assistant", "uuid": "a1", "cwd": str(repo_root),
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "t1", "name": "Bash",
              "input": {"command": "export OPENAI_API_KEY=REDACTED_TEST"}}]}},
        {"type": "system", "subtype": "compact_boundary", "cwd": str(repo_root), "content": "summary"},
    ]
    (projects / "sess-S.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    assert import_claude.run(fresh_repo, out=lambda *a: None, projects_dir=tmp_path / "projects") == 0

    # WHEN the developer runs status
    rc, text = _run(status_cmd.run, fresh_repo)
    assert rc == 0
    assert "CLAUDE_LEDGER" in text
    assert "sess-S" in text and "redactions" in text
    assert "compaction-boundary" in text  # the per-session breakdown
    # the binding §12a compaction-ceiling disclosure sentence is printed verbatim
    assert "unrecoverable by any OpenProof version — the transcript is complete only after the last boundary." in text
    assert "release gate:" in text and "AGGREGATE:" in text
    assert "safe" not in text.lower()  # qualified disclosure only

    # the gate flags the unacknowledged system/compact_boundary unparsed type
    assert "NEEDS_HUMAN_REVIEW" in text

    # AND doctor confirms the safety invariants while a redacted ledger exists locally
    rc, dtext = _run(doctor_cmd.run, fresh_repo)
    assert rc == 0
    assert "All v0.1 safety invariants hold." in dtext
