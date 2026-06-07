"""Frozen v0.1 pins locked as golden vectors.

The spec delegates the literal values of ``spec-version`` and the RawEvent
``schemaVersion`` to the implementation; once chosen they are frozen. Changing either
is a deliberate, reviewed event — this test makes an accidental drift fail loudly.
"""

from __future__ import annotations

from openproof.config import SCHEMA_VERSION, SPEC_VERSION


def test_spec_and_schema_pins_frozen():
    assert SPEC_VERSION == "0.1.0"
    assert SCHEMA_VERSION == 1
