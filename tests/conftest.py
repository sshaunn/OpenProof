"""Shared test fixtures (the build's test sandbox).

Fixtures are small factories — functional-first, per the coding constitution. Every
git-touching test runs in an isolated ``tmp_path`` repo so the suite never depends on
or mutates the real OpenProof working tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from openproof.config import Layout
from openproof.git import repo as gitrepo


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def run_git():
    """Run a raw git command in a repo (for tests that build specific git shapes)."""
    return _git


@pytest.fixture
def fresh_repo(tmp_path) -> Path:
    """A historyless git repo (0 commits) — the live dogfood fresh-repo path."""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    return tmp_path


@pytest.fixture
def committed_repo(fresh_repo) -> Path:
    """A git repo with exactly one root commit."""
    (fresh_repo / "README").write_text("hi", encoding="utf-8")
    _git(["add", "."], fresh_repo)
    _git(["commit", "-m", "first"], fresh_repo)
    return fresh_repo


@pytest.fixture
def layout_of():
    """Resolve a repo path to its ``.openproof/`` Layout through git's realpath toplevel
    (so tests match ``init``'s own toplevel on macOS, where /var is a symlink)."""

    return lambda path: Layout(Path(gitrepo.resolve_toplevel(path)))
