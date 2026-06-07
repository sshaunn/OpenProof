"""Component tests for the transactional staging → committed promote (§10/§12a)."""

from __future__ import annotations

import pytest

from openproof.commands import init as init_cmd
from openproof.commit.promote import promote, reconcile, write_staging
from openproof.commit.snapshot import Snapshot
from openproof.errors import ReceiptCorruptionError
from openproof.git import repo as gitrepo

HASH = "a" * 64


def _snapshot(manifest=b'{"m":1}\n'):
    return Snapshot(HASH, b'{"id":"e"}\n', b"", manifest, ())


def _layout(fresh_repo, layout_of):
    init_cmd.run(fresh_repo, out=lambda *a: None)
    return layout_of(fresh_repo)


def _rel(layout):
    return f".openproof/committed/{HASH}"


def test_write_staging_then_promote(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())
    assert promote(layout, HASH) == "COMMITTED"
    assert (layout.committed / HASH / "manifest.yml").exists()
    assert not (layout.staging / HASH).exists()  # staging consumed by the rename
    assert gitrepo.tracked_under(layout.repo_root, _rel(layout))  # in the git index


def test_idempotent_duplicate(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())
    promote(layout, HASH)
    write_staging(layout, _snapshot())  # identical bytes again
    assert promote(layout, HASH) == "DUPLICATE"
    assert not (layout.staging / HASH).exists()


def test_f5_hard_abort_on_non_identical(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())
    promote(layout, HASH)
    write_staging(layout, _snapshot(manifest=b'{"m":2}\n'))  # SAME hash path, different bytes
    with pytest.raises(ReceiptCorruptionError):
        promote(layout, HASH)


def test_rename_failure_injection_leaves_orphan_then_reconciled(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())

    def crash():
        raise RuntimeError("simulated crash between rename and git add")

    with pytest.raises(RuntimeError):
        promote(layout, HASH, after_rename_hook=crash)

    # the F4 orphan: committed/<hash>/ is present in the working tree but NOT in the index
    assert (layout.committed / HASH).exists()
    assert not gitrepo.tracked_under(layout.repo_root, _rel(layout))

    # the NEXT invocation reconciles it (re-adds the valid receipt)
    notes = reconcile(layout)
    assert any("orphan" in n for n in notes)
    assert gitrepo.tracked_under(layout.repo_root, _rel(layout))


def test_rollback_on_git_add_failure(fresh_repo, layout_of, monkeypatch):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())
    monkeypatch.setattr(gitrepo, "git_add", lambda *a, **k: False)  # simulate git add failure
    with pytest.raises(Exception):
        promote(layout, HASH)
    assert (layout.staging / HASH).exists()       # rolled back to staging
    assert not (layout.committed / HASH).exists()  # nothing committed


def test_reconcile_sweeps_leftover_staging(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())  # an uncatchable-termination residue
    notes = reconcile(layout)
    assert any("staging" in n for n in notes)
    assert not (layout.staging / HASH).exists()


def test_write_staging_overwrites_existing(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot(manifest=b'{"m":1}\n'))
    write_staging(layout, _snapshot(manifest=b'{"m":2}\n'))  # second call clears the stale dir
    assert (layout.staging / HASH / "manifest.yml").read_bytes() == b'{"m":2}\n'


def test_duplicate_readds_an_untracked_orphan(fresh_repo, layout_of):
    layout = _layout(fresh_repo, layout_of)
    write_staging(layout, _snapshot())
    with pytest.raises(RuntimeError):
        promote(layout, HASH, after_rename_hook=lambda: (_ for _ in ()).throw(RuntimeError("crash")))
    # an untracked orphan exists; re-staging the identical receipt → DUPLICATE re-adds it
    write_staging(layout, _snapshot())
    assert promote(layout, HASH) == "DUPLICATE"
    assert gitrepo.tracked_under(layout.repo_root, _rel(layout))
