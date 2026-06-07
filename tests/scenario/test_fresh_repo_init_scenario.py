"""SCENARIO: a developer initializes OpenProof in a brand-new repository.

Mirrors §7 workflow step 1 and the §6a dogfood fresh-repo path. This is the story the
tool actually lived on this repo (0 commits). It asserts user-observable outcomes AND
the safety invariants a second party relies on — not just "the function returned".
"""

from __future__ import annotations

import json
import subprocess

from openproof.commands import init as init_cmd


def _tracked_paths_under(repo, *subpaths) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *subpaths],
        cwd=str(repo),
        capture_output=True,
        text=True,
    ).stdout
    return [p for p in out.splitlines() if p.strip()]


def test_fresh_repo_init_produces_a_safe_bound_ledger(fresh_repo, layout_of):
    # GIVEN a freshly created git repository with no commits yet
    assert _tracked_paths_under(fresh_repo) == []

    # WHEN the developer runs `openproof init`
    lines: list[str] = []
    rc = init_cmd.run(fresh_repo, out=lines.append)

    # THEN it succeeds and reports the binding without crashing on the historyless edge
    assert rc == 0
    assert any("Initialized" in line for line in lines)

    layout = layout_of(fresh_repo)

    # AND the ledger layout exists with the safe-by-default .gitignore in place
    assert layout.root.is_dir()
    assert layout.gitignore.exists()
    gitignore = layout.gitignore.read_text()
    assert all(s in gitignore for s in ("vault/", "raw/", "staging/"))

    # AND the committed fingerprint is the portable historyless literal — never a path-oracle
    config = json.loads(layout.config.read_bytes())
    assert config["repoFingerprint"] == {"status": "unavailable", "reason": "historyless"}
    assert str(fresh_repo) not in layout.config.read_text()

    # AND the safety invariant holds: nothing under raw/vault/staging is tracked (P6)
    assert _tracked_paths_under(fresh_repo, ".openproof/raw", ".openproof/vault", ".openproof/staging") == []


def test_init_is_repeatable_without_clobbering(fresh_repo, layout_of):
    # GIVEN an already-initialized repo
    init_cmd.run(fresh_repo, out=lambda *a: None)
    before = layout_of(fresh_repo).config.read_bytes()

    # WHEN the developer runs init again
    notices: list[str] = []
    rc = init_cmd.run(fresh_repo, out=notices.append)

    # THEN it is a non-destructive no-op
    assert rc == 0
    assert any("already initialized" in n for n in notices)
    assert layout_of(fresh_repo).config.read_bytes() == before
