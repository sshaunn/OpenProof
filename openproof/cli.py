"""``openproof`` CLI — thin arg parsing → command dispatch (plan §3).

The five v0.1 commands are the complete surface: ``init``, ``import claude``,
``status``, ``commit``, ``doctor`` (§10). There is no sixth command. Build-step-1
implements ``init``; the rest are registered stubs so the surface is fixed and the
``import <source>`` dispatch shape exists from the start.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .commands import commit as commit_cmd
from .commands import doctor as doctor_cmd
from .commands import import_claude as import_claude_cmd
from .commands import init as init_cmd
from .commands import status as status_cmd
from .errors import EXIT_ERROR, OpenProofError


def _run_init(args: argparse.Namespace) -> int:
    return init_cmd.run(Path.cwd())


def _run_import_claude(args: argparse.Namespace) -> int:
    return import_claude_cmd.run(Path.cwd())


def _run_status(args: argparse.Namespace) -> int:
    return status_cmd.run(Path.cwd())


def _run_doctor(args: argparse.Namespace) -> int:
    return doctor_cmd.run(Path.cwd())


def _run_commit(args: argparse.Namespace) -> int:
    return commit_cmd.run(Path.cwd(), ack_unparsed=getattr(args, "ack_unparsed", False))


# command key → handler. `import` dispatches on its source subcommand.
_HANDLERS = {
    "init": _run_init,
    "import:claude": _run_import_claude,
    "status": _run_status,
    "commit": _run_commit,
    "doctor": _run_doctor,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openproof", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"openproof {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("init", help="create .openproof/, write .gitignore, pin spec-version, bind repo")

    imp = sub.add_parser("import", help="import a transcript source (Claude only in v0.1)")
    imp_sources = imp.add_subparsers(dest="source", metavar="<source>")
    imp_sources.add_parser("claude", help="discover + normalize Claude Code JSONL")

    sub.add_parser("status", help="binding, counts, unparsed warnings, gate result + disclosure")
    commit = sub.add_parser("commit", help="the only promotion path: gate → staged receipt → committed/")
    commit.add_argument("--ack-unparsed", action="store_true",
                        help="acknowledge unparsed record types (clears N2) before the gate")
    sub.add_parser("doctor", help="read-only diagnostics: re-assert v0.1 safety invariants")
    return parser


def _resolve_handler(args: argparse.Namespace):
    if args.command == "import":
        if getattr(args, "source", None) is None:
            return None
        return _HANDLERS.get(f"import:{args.source}")
    return _HANDLERS.get(args.command)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = _resolve_handler(args)
    if handler is None:
        parser.print_help(sys.stderr)
        return EXIT_ERROR
    try:
        return handler(args)
    except OpenProofError as err:
        print(f"openproof: {err}", file=sys.stderr)
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
