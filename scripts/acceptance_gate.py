"""OpenProof BUILD acceptance gate — the dogfood of §12, applied to our own build.

This is NOT a product command (the v0.1 surface stays exactly five). It is the
development gate the CONSTITUTION requires every build step to pass before it is
"promoted" (considered done / eligible to commit). It mirrors the product's release
gate by design: a registry of deterministic predicates, each returning (status, detail),
with an aggregate PASS only if every predicate PASSes — and a non-zero exit otherwise so
it wires straight into the dev loop / pre-commit / CI.

    python scripts/acceptance_gate.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # run-from-source: make the openproof package importable

PKG_SOURCE_DIRS = [REPO / "openproof", REPO / "scripts"]
TEST_LAYERS = ["tests/unit", "tests/component", "tests/scenario"]
REQUIRED_COMMANDS = {"init", "import", "status", "commit", "doctor"}
REQUIRED_IMPORT_SOURCES = {"claude"}
NEVER_TRACKED = [".openproof/raw", ".openproof/vault", ".openproof/staging"]

# High-signal secret shapes (the §6.5 tier-A families). These deliberately require real
# entropy after the prefix, so pattern-DEFINITION code (regex literals with [ ] { }) and
# keyword *lists* never self-match — verified against this file.
SECRET_SHAPES = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:password|passwd|secret|token|api_key|apikey|access_key|secret_key|"
        r"private_key|client_secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"
    ),
]

PASS, FAIL = "PASS", "FAIL"
_PYTEST: dict = {}


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(REPO), capture_output=True, text=True, **kw)


def _pytest_result() -> dict:
    if not _PYTEST:
        cov_json = REPO / ".gate-coverage.json"
        res = _run(
            [sys.executable, "-m", "pytest", "-q", "--cov=openproof",
             f"--cov-report=json:{cov_json}", "--cov-fail-under=0"]
        )
        pct = None
        if cov_json.exists():
            pct = json.loads(cov_json.read_text())["totals"]["percent_covered"]
            cov_json.unlink()
        lines = res.stdout.strip().splitlines() or [""]
        _PYTEST.update(ok=res.returncode == 0, pct=pct, summary=lines[-1])
    return _PYTEST


def predicate_tests():
    r = _pytest_result()
    return (PASS, r["summary"]) if r["ok"] else (FAIL, f"suite not green — {r['summary']}")


def predicate_coverage():
    pct = _pytest_result()["pct"]
    if pct is None:
        return FAIL, "no coverage data produced"
    return (PASS, f"line coverage {pct:.2f}%") if pct >= 100 else (FAIL, f"line coverage {pct:.2f}% < 100%")


def predicate_test_layers():
    missing = [d for d in TEST_LAYERS if not list((REPO / d).glob("test_*.py"))]
    return (FAIL, f"missing/empty layer(s): {missing}") if missing else (
        PASS, "unit + component + scenario all present",
    )


def predicate_safety_p6():
    tracked = [ln for ln in _run(["git", "ls-files", *NEVER_TRACKED]).stdout.splitlines() if ln.strip()]
    return (FAIL, f"tracked payload: {tracked}") if tracked else (
        PASS, "raw/ vault/ staging/ never tracked",
    )


def predicate_no_secret_in_source():
    hits = [
        f"{py.relative_to(REPO)} ~ /{rx.pattern[:18]}.../"
        for base in PKG_SOURCE_DIRS
        for py in base.rglob("*.py")
        for rx in SECRET_SHAPES
        if rx.search(py.read_text(encoding="utf-8"))
    ]
    return (FAIL, f"possible secret literal(s): {hits}") if hits else (
        PASS, "no secret literal in tool source",
    )


def predicate_command_surface():
    from openproof.cli import _build_parser

    parser = _build_parser()
    subs = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    commands = set(subs.choices)
    imp = subs.choices.get("import")
    imp_subs = next((a for a in imp._actions if isinstance(a, argparse._SubParsersAction)), None) if imp else None
    sources = set(imp_subs.choices) if imp_subs else set()
    if commands != REQUIRED_COMMANDS:
        return FAIL, f"command surface drifted: {sorted(commands)}"
    if sources != REQUIRED_IMPORT_SOURCES:
        return FAIL, f"import sources drifted: {sorted(sources)}"
    return PASS, "exactly init / import(claude) / status / commit / doctor"


GATE_PREDICATES = [
    ("B1 tests green", predicate_tests),
    ("B2 coverage 100%", predicate_coverage),
    ("B3 test layers present", predicate_test_layers),
    ("B4 payload never tracked (P6)", predicate_safety_p6),
    ("B5 no secret in tool source", predicate_no_secret_in_source),
    ("B6 frozen 5-command surface", predicate_command_surface),
]


def main() -> int:
    results = [(name, *fn()) for name, fn in GATE_PREDICATES]
    width = max(len(name) for name, _, _ in results)
    print("OpenProof build acceptance gate")
    print("=" * 72)
    for name, status, detail in results:
        mark = "PASS" if status == PASS else "FAIL"
        print(f"  [{mark}] {name.ljust(width)}  — {detail}")
    aggregate = PASS if all(status == PASS for _, status, _ in results) else FAIL
    print("=" * 72)
    print(f"  AGGREGATE: {aggregate}")
    return 0 if aggregate == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
