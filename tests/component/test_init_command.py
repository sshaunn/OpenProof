"""Component tests for ``openproof init`` (§10, §17 task 1).

Exercises the command end-to-end against real git repos in a sandbox: the layout it
writes, the historyless vs with-history fingerprint, idempotence, and the N1 unbound path.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from openproof.canonical import canonical_bytes
from openproof.commands import init as init_cmd
from openproof.config import SPEC_VERSION
from openproof.errors import UnboundRepoError


def test_writes_layout_and_historyless_fingerprint(fresh_repo, layout_of):
    assert init_cmd.run(fresh_repo, out=lambda *a: None) == 0

    layout = layout_of(fresh_repo)
    for surface in ("vault/", "raw/", "staging/"):
        assert surface in layout.gitignore.read_text()
    assert "index.cache" in layout.gitignore.read_text()
    assert layout.spec_version.read_text(encoding="utf-8") == SPEC_VERSION + "\n"

    expected = (
        canonical_bytes({"repoFingerprint": {"status": "unavailable", "reason": "historyless"}})
        + b"\n"
    )
    assert layout.config.read_bytes() == expected


def test_with_history_records_portable_identity(committed_repo, layout_of):
    assert init_cmd.run(committed_repo, out=lambda *a: None) == 0
    identity = json.loads(layout_of(committed_repo).config.read_bytes())["repoFingerprint"]
    # exact key set — any extra field on the git-TRACKED published config must fail
    assert set(identity.keys()) == {"status", "gitObjectFormat", "rootCommits"}
    assert identity["status"] == "available"
    assert identity["gitObjectFormat"] in ("sha1", "sha256")
    assert len(identity["rootCommits"]) == 1
    assert len(identity["rootCommits"][0]) in (40, 64)


def test_config_leaks_no_machine_path(committed_repo, layout_of):
    # config.yml is git-TRACKED → it must carry no absolute path / no localDiscoveryKey
    init_cmd.run(committed_repo, out=lambda *a: None)
    raw = layout_of(committed_repo).config.read_bytes().decode()
    assert str(committed_repo) not in raw
    assert "/" not in json.loads(raw)["repoFingerprint"].get("status", "")
    assert "localDiscoveryKey" not in raw


def test_idempotent_second_run_is_noop(fresh_repo, layout_of):
    assert init_cmd.run(fresh_repo, out=lambda *a: None) == 0
    before = layout_of(fresh_repo).config.read_bytes()
    assert init_cmd.run(fresh_repo, out=lambda *a: None) == 0
    assert layout_of(fresh_repo).config.read_bytes() == before


def test_unbound_outside_git_raises_n1(tmp_path):
    with pytest.raises(UnboundRepoError):
        init_cmd.run(tmp_path, out=lambda *a: None)


def _ls_files(repo, *paths) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *paths], cwd=str(repo), capture_output=True, text=True
    ).stdout
    return [p for p in out.splitlines() if p.strip()]


def test_init_gitignore_actually_makes_payload_dirs_untracked(fresh_repo, layout_of):
    # The P6 guarantee, non-vacuously: a developer's blanket `git add .` must promote NO
    # transcript payload — exercised against REAL git, without the unbuilt import/commit.
    assert init_cmd.run(fresh_repo, out=lambda *a: None) == 0
    layout = layout_of(fresh_repo)
    for p in (
        layout.raw / "claude" / "s.jsonl",
        layout.vault / "secrets-map.json",
        layout.staging / "h" / "events.jsonl",
    ):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("payload", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(fresh_repo), check=True, capture_output=True)
    assert _ls_files(fresh_repo, ".openproof/raw", ".openproof/vault", ".openproof/staging") == []

    # complementary: committed/ is NOT ignored (it is the one trackable transcript surface)
    check = subprocess.run(
        ["git", "check-ignore", ".openproof/committed/h/events.jsonl"],
        cwd=str(fresh_repo),
        capture_output=True,
        text=True,
    )
    assert check.returncode != 0  # not ignored


def test_init_from_subdirectory_writes_at_repo_toplevel(committed_repo, layout_of):
    # binding resolves the canonical toplevel: init from a nested subdir must write
    # .openproof/ at the repo ROOT, never under the invocation cwd (§6 item 7 / §17 task 5)
    repo_root = layout_of(committed_repo).repo_root
    sub = repo_root / "a" / "b"
    sub.mkdir(parents=True)
    assert init_cmd.run(sub, out=lambda *a: None) == 0
    assert (repo_root / ".openproof" / "config.yml").exists()
    assert not (sub / ".openproof").exists()
