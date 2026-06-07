"""Repository binding + the committed ``repositoryIdentity`` object (§12c item 3, §6 item 7).

This is the *minimal* git surface ``init`` needs to record the repo fingerprint. The
committed identity is the PORTABLE one — never the local absolute path:

  * a repo WITH history →
    ``{status:"available", gitObjectFormat:"sha1"|"sha256",
       rootCommits:[<root-commit ids sorted ascending by lowercase ASCII-hex>]}``;
  * a fresh/historyless repo → the literal ``{status:"unavailable", reason:"historyless"}``
    (never null, empty, or any path-derived value).

The full git-evidence collector (GitChangeSet, the pinned first-parent diff policy)
is build-step-5; it is intentionally not here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = [
    "git_available",
    "is_git_repo",
    "resolve_toplevel",
    "has_commits",
    "object_format",
    "root_commits",
    "repository_identity",
]


def _git(args: list[str], cwd: Path | str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def git_available() -> bool:
    try:
        return _git(["--version"], Path.cwd()).returncode == 0
    except FileNotFoundError:  # pragma: no cover - defensive: git absent from PATH
        return False


def is_git_repo(cwd: Path | str) -> bool:
    r = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    return r.returncode == 0 and r.stdout.strip() == "true"


def resolve_toplevel(cwd: Path | str) -> str | None:
    """Canonical absolute repository toplevel (LOCAL-ONLY; never committed)."""
    r = _git(["rev-parse", "--show-toplevel"], cwd)
    return r.stdout.strip() if r.returncode == 0 else None


def has_commits(cwd: Path | str) -> bool:
    return _git(["rev-parse", "--verify", "HEAD"], cwd).returncode == 0


def object_format(cwd: Path | str) -> str:
    r = _git(["rev-parse", "--show-object-format"], cwd)
    fmt = r.stdout.strip() if r.returncode == 0 else ""
    return fmt or "sha1"


def root_commits(cwd: Path | str) -> list[str]:
    """All parentless root commits reachable from HEAD, ascending by lowercase ASCII-hex."""
    r = _git(["rev-list", "--max-parents=0", "HEAD"], cwd)
    if r.returncode != 0:
        return []
    return sorted(line.strip().lower() for line in r.stdout.splitlines() if line.strip())


def repository_identity(cwd: Path | str) -> dict:
    """The §12c item-3 ``repositoryIdentity`` object — the portable committed fingerprint."""
    if not has_commits(cwd):
        return {"status": "unavailable", "reason": "historyless"}
    return {
        "status": "available",
        "gitObjectFormat": object_format(cwd),
        "rootCommits": root_commits(cwd),
    }
