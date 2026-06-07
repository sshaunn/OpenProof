"""Unit tests for the ``.openproof/`` path Layout (openproof/config.py)."""

from __future__ import annotations

from pathlib import Path

from openproof.config import OPENPROOF_DIRNAME, Layout


def test_layout_paths_are_under_openproof_dir():
    layout = Layout(Path("/repo"))
    assert layout.root == Path("/repo") / OPENPROOF_DIRNAME
    assert layout.gitignore == layout.root / ".gitignore"
    assert layout.spec_version == layout.root / "spec-version"
    assert layout.config == layout.root / "config.yml"
    assert layout.raw == layout.root / "raw"
    assert layout.vault == layout.root / "vault"
    assert layout.staging == layout.root / "staging"
    assert layout.committed == layout.root / "committed"
    assert layout.sessions == layout.root / "sessions"
    assert layout.git_changesets == layout.root / "git" / "changesets.yml"


def test_exists_reflects_config_presence(tmp_path):
    layout = Layout(tmp_path)
    assert layout.exists() is False
    layout.root.mkdir()
    layout.config.write_text("{}", encoding="utf-8")
    assert layout.exists() is True
