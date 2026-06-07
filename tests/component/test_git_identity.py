"""Component tests for the minimal git identity slice (openproof/git/repo.py).

The §12c item-3 ``repositoryIdentity`` across the shapes ``init`` must handle: fresh,
single-root, multi-root, plus the read-only helpers — against real git in a sandbox.
"""

from __future__ import annotations

import subprocess

from openproof.git import repo as gitrepo


def _current_branch(repo) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_git_available():
    assert gitrepo.git_available() is True


def test_fresh_repo_is_historyless(fresh_repo):
    assert gitrepo.has_commits(fresh_repo) is False
    assert gitrepo.root_commits(fresh_repo) == []  # rev-list fails → empty, no crash
    assert gitrepo.repository_identity(fresh_repo) == {
        "status": "unavailable",
        "reason": "historyless",
    }


def test_non_repo_is_not_bound(tmp_path):
    assert gitrepo.is_git_repo(tmp_path) is False
    assert gitrepo.resolve_toplevel(tmp_path) is None


def test_single_root_identity(committed_repo):
    identity = gitrepo.repository_identity(committed_repo)
    # pin the available branch by exact shape (mirrors the full-equality unavailable pin)
    assert set(identity.keys()) == {"status", "gitObjectFormat", "rootCommits"}
    assert identity["status"] == "available"
    assert identity["gitObjectFormat"] in ("sha1", "sha256")
    assert len(identity["rootCommits"]) == 1


def test_multi_root_identity_is_sorted_lowercase_array(fresh_repo, run_git):
    # root A on the default branch
    (fresh_repo / "a").write_text("a", encoding="utf-8")
    run_git(["add", "-A"], fresh_repo)
    run_git(["commit", "-m", "root-a"], fresh_repo)
    main_branch = _current_branch(fresh_repo)

    # an independent root B (orphan), then merge unrelated histories so HEAD reaches both
    run_git(["checkout", "--orphan", "branchb"], fresh_repo)
    (fresh_repo / "a").unlink()
    (fresh_repo / "b").write_text("b", encoding="utf-8")
    run_git(["add", "-A"], fresh_repo)
    run_git(["commit", "-m", "root-b"], fresh_repo)

    run_git(["checkout", main_branch], fresh_repo)
    run_git(["merge", "--allow-unrelated-histories", "--no-edit", "branchb"], fresh_repo)

    roots = gitrepo.repository_identity(fresh_repo)["rootCommits"]
    assert len(roots) == 2
    assert roots == sorted(roots)  # ascending by lowercase ASCII-hex
    assert all(r == r.lower() for r in roots)
