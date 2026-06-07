# OpenProof dev loop (CONSTITUTION §2: dev → test → review).
.PHONY: help install test cov gate loop

help:
	@echo "make install  - install the package + dev tools (editable)"
	@echo "make test     - run the full test suite (unit + component + scenario + golden)"
	@echo "make cov      - run tests with a 100% line-coverage gate"
	@echo "make gate     - run the build acceptance gate (the dogfood of §12)"
	@echo "make loop     - cov + gate (the per-step review)"

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

cov:
	python -m pytest --cov=openproof --cov-report=term-missing --cov-fail-under=100

gate:
	python scripts/acceptance_gate.py

loop: cov gate
