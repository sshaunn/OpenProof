"""Guard against a broken install: the package config must ship EVERY openproof sub-package.

v0.1 shipped a broken wheel once — the explicit ``packages = [...]`` list omitted the
sub-packages added in later build steps, so ``import openproof.gate`` failed for anyone who
``pip install``ed it (the source-tree tests never noticed). These tests catch that class of
regression without building a wheel; CI additionally installs the real wheel and smoke-tests it.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from setuptools import find_packages

import openproof

REPO = Path(__file__).resolve().parents[2]


def test_every_subpackage_is_discoverable():
    on_disk = {
        ".".join(p.relative_to(REPO).parts[:-1])
        for p in (REPO / "openproof").rglob("__init__.py")
    }
    discovered = set(find_packages(where=str(REPO), include=["openproof*"]))
    assert on_disk == discovered, f"packaging drift — not discovered: {on_disk - discovered}"


def test_every_submodule_imports():
    # a broken cross-import (the missing-gate symptom) surfaces as an import failure here
    failures = []
    for module in pkgutil.walk_packages(openproof.__path__, prefix="openproof."):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - report any import failure
            failures.append((module.name, repr(exc)))
    assert not failures, failures
