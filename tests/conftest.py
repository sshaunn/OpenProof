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


@pytest.fixture
def fake():
    """Builders for secret-SHAPED test inputs assembled at RUNTIME from inert fragments.

    CONSTITUTION (no-committed-secret rule): NO source file may contain a contiguous
    secret-shaped token — even a fake one — because a secret scanner (GitHub's or our own
    gate's B5) flags the SHAPE, not the realness. So provider keys, connection-string
    credentials, PEM blocks, JWTs, and Bearer tokens are built here from split fragments.
    """

    _begin = "-----BEGIN RSA PRIVATE" + " KEY-----"
    _end = "-----END RSA PRIVATE" + " KEY-----"

    class Fake:
        provider_key = staticmethod(lambda prefix, n=36, ch="A": prefix + ch * n)
        conn = staticmethod(
            lambda scheme="postgres", user="user", pw="pw", host="host", tail="":
            f"{scheme}://{user}:{pw}@{host}{tail}"
        )
        pem = staticmethod(lambda body="MIIbody": _begin + "\n" + body + "\n" + _end)
        jwt = staticmethod(lambda h="hdr", p="pld", s="sig": "eyJ" + h + ".eyJ" + p + "." + s)
        bearer = staticmethod(lambda tok="tok_abcdef": "Bearer " + tok)

    return Fake()
