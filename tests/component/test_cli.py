"""Component tests for the CLI dispatcher (openproof/cli.py).

Exercises the whole arg-parse → dispatch surface through ``cli.main(argv)``: the five
commands, the ``import <source>`` sub-dispatch, the no-command/no-source help paths, and
the typed-error → exit-code mapping.
"""

from __future__ import annotations

import pytest

from openproof import cli
from openproof.errors import EXIT_ERROR, EXIT_OK, EXIT_UNBOUND


def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "openproof" in capsys.readouterr().out


def test_init_dispatches_and_succeeds(fresh_repo, monkeypatch, capsys):
    monkeypatch.chdir(fresh_repo)
    assert cli.main(["init"]) == EXIT_OK
    assert "Initialized" in capsys.readouterr().out


def test_init_unbound_maps_to_exit_code(tmp_path, monkeypatch, capsys):
    # tmp_path is not a git repo → UnboundRepoError → EXIT_UNBOUND, no crash
    monkeypatch.chdir(tmp_path)
    assert cli.main(["init"]) == EXIT_UNBOUND
    assert "openproof:" in capsys.readouterr().err


def test_commit_dispatches(fresh_repo, monkeypatch, capsys):
    # all five commands are implemented now; commit without init exits cleanly (NotInitialized)
    monkeypatch.chdir(fresh_repo)
    assert cli.main(["commit"]) == 4  # EXIT_NOT_INITIALIZED


@pytest.mark.parametrize("command", ["status", "doctor"])
def test_status_and_doctor_dispatch(command, fresh_repo, monkeypatch, capsys):
    monkeypatch.chdir(fresh_repo)
    from openproof.commands import init as init_cmd

    init_cmd.run(fresh_repo, out=lambda *a: None)
    assert cli.main([command]) == 0


def test_import_claude_dispatches(fresh_repo, tmp_path, monkeypatch, capsys):
    # `import claude` is implemented; with no Claude sessions for this repo it exits cleanly
    monkeypatch.chdir(fresh_repo)
    from openproof.commands import import_claude
    from openproof.commands import init as init_cmd

    init_cmd.run(fresh_repo, out=lambda *a: None)
    monkeypatch.setattr(import_claude, "_claude_projects_dir", lambda: tmp_path / "none")
    assert cli.main(["import", "claude"]) == 0
    assert "No Claude sessions" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert cli.main([]) == EXIT_ERROR
    assert "usage" in capsys.readouterr().err.lower()


def test_import_without_source_prints_help(capsys):
    assert cli.main(["import"]) == EXIT_ERROR
    assert "usage" in capsys.readouterr().err.lower()


def test_unknown_source_is_rejected_by_argparse(capsys):
    # argparse rejects an unregistered source choice with exit code 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["import", "codex"])
    assert exc.value.code == 2


@pytest.mark.parametrize("command", ["review", "export", "task", "pack", "gate", "frobnicate"])
def test_unknown_command_is_rejected_by_argparse(command, capsys):
    # the five v0.1 commands are the only surface (§10/§6/§17): any unregistered command —
    # a deferred fast-follow name or a typo — must be rejected, never silently accepted
    with pytest.raises(SystemExit) as exc:
        cli.main([command])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err.lower()
