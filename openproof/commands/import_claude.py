"""``openproof import claude`` — discover + import Claude JSONL for this repo (§17 task 4).

Discovery is the §6 item-7 executable LOCAL algorithm: scan ``~/.claude/projects/*/`` and
match each session by resolving its records' ``cwd`` to this repository's toplevel (never a
hash-keyed path lookup). Each matched session is imported (boundary → normalize → redact →
content-address) and written to the gitignored ``raw/`` + ``vault/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import SCHEMA_VERSION, Layout
from ..errors import EXIT_OK, NotInitializedError, UnboundRepoError
from ..git import repo as gitrepo
from ..ledger.boundary import P4_REWRITTEN, compare_boundary
from ..ledger.importer import import_session
from ..ledger.store import read_boundary, write_boundary, write_session

__all__ = ["run", "discover"]


def _claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


_META_SCAN_LIMIT = 200  # the cwd is recorded a few records in (the first records can be meta)


def _session_meta(path: Path):
    """Stream the early records and return ``(cwd, sessionId, version)`` — scanning for the
    first record that carries a ``cwd`` (it is not always the first record)."""
    cwd = session_id = version = None
    with path.open(encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            if index >= _META_SCAN_LIMIT:
                break
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            cwd = cwd or record.get("cwd")
            session_id = session_id or record.get("sessionId")
            version = version or record.get("version")
            if cwd:
                break
    return cwd, session_id, version


def discover(projects_dir: Path, repo_root: Path) -> list:
    """Return ``(path, session_id, source_version)`` for sessions whose ``cwd`` resolves to ``repo_root``."""
    if not projects_dir.exists():
        return []
    real_root = str(Path(repo_root).resolve())
    matches = []
    for path in sorted(projects_dir.glob("*/*.jsonl")):
        cwd, session_id, version = _session_meta(path)
        if not cwd or not Path(cwd).is_dir():  # a session recorded on another machine/path
            continue
        toplevel = gitrepo.resolve_toplevel(cwd)
        if toplevel and str(Path(toplevel).resolve()) == real_root:
            matches.append((path, session_id or path.stem, version))
    return matches


def run(cwd: Path | str = ".", *, out=print, projects_dir: Path | None = None) -> int:
    cwd = Path(cwd)
    if not gitrepo.is_git_repo(cwd):
        raise UnboundRepoError(f"{cwd} is not inside a git repository — cannot bind.")
    repo_root = Path(gitrepo.resolve_toplevel(cwd))
    layout = Layout(repo_root)
    if not layout.exists():
        raise NotInitializedError("`.openproof/` not found — run `openproof init` first.")

    matches = discover(projects_dir or _claude_projects_dir(), repo_root)
    if not matches:
        out("No Claude sessions found for this repository (GIT_ONLY_EVIDENCE).")
        return EXIT_OK

    total_events = 0
    for path, session_id, version in matches:
        data = path.read_bytes()
        prior = read_boundary(layout, "claude_jsonl", session_id)
        if prior is not None and compare_boundary(prior, data) == P4_REWRITTEN:
            out(f"  {session_id}: source prefix REWRITTEN since last import — quarantined (needs review), skipped")
            continue
        outcome = import_session(
            "claude_jsonl", session_id, data,
            schema_version=SCHEMA_VERSION, file_identity=str(path), source_version=version,
        )
        write_session(
            layout, "claude_jsonl", session_id,
            raw_lines=outcome.raw_lines, unredacted_lines=outcome.unredacted_lines,
            vault_map=outcome.vault_map, session=outcome.session,
            unparsed_records=outcome.unparsed_records,
        )
        write_boundary(layout, outcome.boundary)  # §12a: persist so a later import can classify (P4)
        s = outcome.session
        out(f"  {session_id}: {s.event_count} events / {s.source_record_count} records "
            f"({s.unparsed_record_count} unparsed, {sum(s.redaction_summary.values())} redactions)")
        total_events += s.event_count

    out(f"Imported {len(matches)} session(s), {total_events} events → {layout.raw} (local, gitignored).")
    return EXIT_OK
