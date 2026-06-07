"""Component tests for `import claude` discovery + edge handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openproof.commands import import_claude
from openproof.commands import init as init_cmd
from openproof.errors import UnboundRepoError
from openproof.ledger.store import read_raw_lines


def _session(folder: Path, name: str, records):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_default_projects_dir_is_under_home():
    assert import_claude._claude_projects_dir() == Path.home() / ".claude" / "projects"


def test_discover_matches_only_this_repo(fresh_repo, layout_of, tmp_path):
    repo_root = layout_of(fresh_repo).repo_root
    projects = tmp_path / "projects"
    _session(projects / "a", "mine", [{"type": "user", "uuid": "u1", "cwd": str(repo_root), "sessionId": "mine"}])
    _session(projects / "b", "other", [{"type": "user", "uuid": "u2", "cwd": "/nonexistent/elsewhere"}])
    matches = import_claude.discover(projects, repo_root)
    assert [m[1] for m in matches] == ["mine"]


def test_discover_skips_a_foreign_repo(fresh_repo, layout_of, tmp_path, run_git):
    # a session whose cwd is a VALID directory inside a DIFFERENT git repo must NOT match
    repo_root = layout_of(fresh_repo).repo_root
    other = tmp_path / "other-repo"
    other.mkdir()
    run_git(["init"], other)
    projects = tmp_path / "projects"
    _session(projects / "mine", "mine", [{"type": "user", "uuid": "u1", "cwd": str(repo_root)}])
    _session(projects / "foreign", "foreign", [{"type": "user", "uuid": "u2", "cwd": str(other)}])
    matches = import_claude.discover(projects, repo_root)
    assert [m[1] for m in matches] == ["mine"]  # the foreign-repo session is excluded


def test_discover_skips_malformed_and_cwdless_sessions(fresh_repo, layout_of, tmp_path):
    repo_root = layout_of(fresh_repo).repo_root
    projects = tmp_path / "projects"
    (projects / "x").mkdir(parents=True)
    (projects / "x" / "malformed.jsonl").write_text("not json at all\n", encoding="utf-8")
    (projects / "x" / "empty.jsonl").write_text("\n\n", encoding="utf-8")
    _session(projects / "y", "nocwd", [{"type": "user", "uuid": "u1"}])  # first record has no cwd
    assert import_claude.discover(projects, repo_root) == []


def test_discover_returns_empty_when_projects_dir_absent(fresh_repo, layout_of, tmp_path):
    assert import_claude.discover(tmp_path / "missing", layout_of(fresh_repo).repo_root) == []


def test_run_outside_git_is_unbound(tmp_path):
    with pytest.raises(UnboundRepoError):
        import_claude.run(tmp_path, out=lambda *a: None, projects_dir=tmp_path / "none")


def test_read_raw_lines_absent_is_empty(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    assert read_raw_lines(layout_of(fresh_repo), "claude_jsonl", "nope") == b""


def test_read_unparsed_absent_is_empty(fresh_repo, layout_of):
    from openproof.ledger.store import read_unparsed

    init_cmd.run(fresh_repo, out=lambda *a: None)
    assert read_unparsed(layout_of(fresh_repo), "claude_jsonl", "nope") == []
