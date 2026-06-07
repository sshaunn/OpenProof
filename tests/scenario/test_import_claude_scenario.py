"""SCENARIO: a developer runs `openproof import claude` on their project.

Mirrors §7 step 2: discover the repo's Claude sessions, redact at the boundary, and write
a local (gitignored) redacted ledger. The story asserts the user-observable outcome AND
the safety invariants: the secret is neutralized, the original is vault-only, and nothing
under raw/ or vault/ is tracked.
"""

from __future__ import annotations

import json
import subprocess

from openproof.commands import import_claude
from openproof.commands import init as init_cmd


def _write_session(projects_dir, repo_root, session_id, records):
    folder = projects_dir / "slug"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session_id}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def test_import_claude_writes_a_redacted_ledger(fresh_repo, layout_of, tmp_path):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    repo_root = layout.repo_root
    projects = tmp_path / "projects"

    records = [
        {"type": "user", "uuid": "u1", "cwd": str(repo_root), "sessionId": "sess-A", "version": "1.0",
         "message": {"role": "user", "content": "set up the db"}},
        {"type": "assistant", "uuid": "a1", "cwd": str(repo_root),
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "tu1", "name": "Bash",
              "input": {"command": "export DB_PASSWORD=REDACTED_TEST && psql"}}]}},
    ]
    _write_session(projects, repo_root, "sess-A", records)

    lines = []
    rc = import_claude.run(fresh_repo, out=lines.append, projects_dir=projects)
    assert rc == 0
    assert any("Imported 1 session" in line for line in lines)

    # WHEN imported, the redacted ledger exists and the secret is neutralized
    raw_file = layout.raw / "claude_jsonl" / "sess-A.jsonl"
    assert raw_file.exists()
    assert "REDACTED_TEST" not in raw_file.read_text(encoding="utf-8")

    # the original lives ONLY in the vault (reversible, local)
    secrets = json.loads((layout.vault / "secrets-map.json").read_text(encoding="utf-8"))
    assert any(v["original"] == "REDACTED_TEST" for v in secrets.values())

    # the unredacted mirror is written (the reversibility surface) and DOES hold the original
    mirror = layout.vault / "raw-unredacted" / "claude_jsonl" / "sess-A.jsonl"
    assert mirror.exists()
    assert "REDACTED_TEST" in mirror.read_text(encoding="utf-8")

    # the frozen boundary is persisted (LOCAL-ONLY, under gitignored raw/) so P4 can run later
    assert (layout.boundaries / "claude_jsonl-sess-A.json").exists()

    # the per-session summary is written (tracked metadata)
    assert (layout.sessions / "claude_jsonl-sess-A.yml").exists()

    # P6: nothing under raw/ or vault/ is tracked
    tracked = subprocess.run(
        ["git", "ls-files", ".openproof/raw", ".openproof/vault"],
        cwd=str(repo_root), capture_output=True, text=True,
    ).stdout
    assert tracked.strip() == ""


def test_reimport_detects_in_place_rewrite(fresh_repo, layout_of, tmp_path):
    # §12a P4: a session import persists the boundary; a later import over a REWRITTEN prefix
    # (same length, different bytes) is detected via the local digest and quarantined.
    init_cmd.run(fresh_repo, out=lambda *a: None)
    repo_root = layout_of(fresh_repo).repo_root
    projects = tmp_path / "projects"
    base = {"type": "user", "uuid": "u1", "cwd": str(repo_root), "sessionId": "sess-R",
            "message": {"role": "user", "content": "AAAA"}}
    _write_session(projects, repo_root, "sess-R", [base])
    assert import_claude.run(fresh_repo, out=lambda *a: None, projects_dir=projects) == 0

    # rewrite the source in place (same byte length, different content) and re-import
    rewritten = {**base, "message": {"role": "user", "content": "BBBB"}}
    _write_session(projects, repo_root, "sess-R", [rewritten])
    lines = []
    assert import_claude.run(fresh_repo, out=lines.append, projects_dir=projects) == 0
    assert any("REWRITTEN" in line and "quarantined" in line for line in lines)


def test_import_without_sessions_is_git_only(fresh_repo, tmp_path):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    lines = []
    rc = import_claude.run(fresh_repo, out=lines.append, projects_dir=tmp_path / "empty")
    assert rc == 0
    assert any("No Claude sessions" in line for line in lines)


def test_import_requires_init(fresh_repo, tmp_path):
    from openproof.errors import NotInitializedError
    import pytest

    with pytest.raises(NotInitializedError):
        import_claude.run(fresh_repo, out=lambda *a: None, projects_dir=tmp_path / "empty")
