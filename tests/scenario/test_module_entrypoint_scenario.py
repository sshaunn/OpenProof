"""SCENARIO: OpenProof runs as a real installed CLI.

Drives the tool the way a user does — as a subprocess — to prove the packaging and
entry point work end-to-end, not just the importable functions.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(args, cwd):
    # the package is run from source (not installed), so put the repo root on the path
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "openproof", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )


def test_module_reports_version():
    result = _run(["--version"], REPO_ROOT)
    assert result.returncode == 0
    assert result.stdout.strip().startswith("openproof")


def test_init_via_real_cli_in_fresh_repo(fresh_repo):
    # WHEN the user runs `python -m openproof init` in their repo
    result = _run(["init"], fresh_repo)

    # THEN it succeeds and writes the ledger files the developer can see
    assert result.returncode == 0, result.stderr
    assert "Initialized" in result.stdout
    assert (fresh_repo / ".openproof" / "config.yml").exists()
    assert (fresh_repo / ".openproof" / "spec-version").exists()
    assert (fresh_repo / ".openproof" / ".gitignore").exists()


def test_commit_without_init_fails_cleanly(fresh_repo):
    # commit is implemented; without init it exits cleanly with the guidance (no traceback)
    result = _run(["commit"], fresh_repo)
    assert result.returncode != 0
    assert "init" in result.stderr.lower()
    assert "Traceback" not in result.stderr
