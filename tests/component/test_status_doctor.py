"""Component tests for `openproof status` and `openproof doctor`."""

from __future__ import annotations

import pytest

from openproof.commands import doctor as doctor_cmd
from openproof.commands import init as init_cmd
from openproof.commands import status as status_cmd
from openproof.commands.doctor import diagnostics
from openproof.errors import NotInitializedError


def _lines(fn, *a, **kw):
    out = []
    rc = fn(*a, out=out.append, **kw)
    return rc, "\n".join(out)


def test_status_git_only_when_no_sessions(fresh_repo):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    rc, text = _lines(status_cmd.run, fresh_repo)
    assert rc == 0
    assert "GIT_ONLY_EVIDENCE" in text
    assert "AGGREGATE: PASS" in text
    assert "No transcript records were imported; this receipt contains git evidence only." in text
    assert "NOT guaranteed" in text  # the qualified disclosure, never an unqualified "safe"
    assert "safe" not in text.lower()


def test_status_requires_init(fresh_repo):
    with pytest.raises(NotInitializedError):
        status_cmd.run(fresh_repo, out=lambda *a: None)


def test_doctor_all_invariants_hold(fresh_repo):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    rc, text = _lines(doctor_cmd.run, fresh_repo)
    assert rc == 0
    assert "All v0.1 safety invariants hold." in text


def test_doctor_detects_tracked_payload(fresh_repo, layout_of, run_git):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    raw = layout.raw / "claude_jsonl" / "s.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("payload", encoding="utf-8")
    run_git(["add", "-f", str(raw)], layout.repo_root)
    rc, text = _lines(doctor_cmd.run, fresh_repo)
    assert rc != 0
    assert "INVARIANT VIOLATION" in text and "TRACKED" in text


def test_doctor_detects_orphan_committed(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    (layout.committed / "deadbeef").mkdir(parents=True)  # untracked orphan receipt dir
    checks = diagnostics(layout)
    orphan = next(c for c in checks if "orphan" in c[0])
    assert orphan[1] is False


def test_diagnostics_flags_missing_gitignore_and_config(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    layout.gitignore.write_text("# nothing excluded\n", encoding="utf-8")
    layout.config.unlink()
    checks = {name: ok for name, ok, _ in diagnostics(layout)}
    assert checks[".gitignore excludes vault/ raw/ staging/"] is False
    assert checks["config.yml + spec-version present"] is False


@pytest.mark.parametrize("present", [("raw/", "staging/"), ("vault/", "staging/"), ("vault/", "raw/")])
def test_gitignore_check_requires_all_three_tokens(fresh_repo, layout_of, present):
    # omitting ANY one of vault//raw//staging/ must fail the exclusion check (all-of, not any-of)
    init_cmd.run(fresh_repo, out=lambda *a: None)
    layout = layout_of(fresh_repo)
    layout.gitignore.write_text("\n".join(present) + "\n", encoding="utf-8")
    checks = {name: ok for name, ok, _ in diagnostics(layout)}
    assert checks[".gitignore excludes vault/ raw/ staging/"] is False


def test_doctor_requires_init(fresh_repo):
    with pytest.raises(NotInitializedError):
        doctor_cmd.run(fresh_repo, out=lambda *a: None)


def test_status_and_doctor_unbound_outside_git(tmp_path):
    from openproof.errors import UnboundRepoError

    with pytest.raises(UnboundRepoError):
        status_cmd.run(tmp_path, out=lambda *a: None)
    with pytest.raises(UnboundRepoError):
        doctor_cmd.run(tmp_path, out=lambda *a: None)
