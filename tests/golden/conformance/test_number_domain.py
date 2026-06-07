"""§17 task-10 number-domain conformance set (the cross-implementation vectors).

Any conforming emitter must reproduce these byte-for-byte under the §12c frozen
encoding: exact big integers (no binary64 collapse), positional shortest-round-trip
non-integers, over-precision rejection, ``-0`` → ``0``, and non-finite rejection.
"""

from __future__ import annotations

import pytest

from openproof.canonical.numbers import NumberError, RawNumber, format_number


def fn(token: str) -> str:
    return format_number(RawNumber(token))


def test_2_53_boundary_commits_exact():
    assert fn("9007199254740991") == "9007199254740991"  # 2^53 - 1
    assert fn("9007199254740992") == "9007199254740992"  # 2^53


def test_2_53_plus_one_not_collapsed():
    # The headline losslessness req: 2^53+1 commits as its exact integer literal,
    # never silently rounded into the binary64 collision 9007199254740992.
    assert fn("9007199254740993") == "9007199254740993"
    assert fn("9007199254740993") != fn("9007199254740992")


def test_very_large_tool_input_integer_exact():
    big = "9" * 80
    assert fn(big) == big


def test_over_precision_non_integer_fails():
    with pytest.raises(NumberError):
        fn("1.0000000000000001")


def test_supported_non_integers_positional_shortest():
    assert fn("0.1") == "0.1"
    assert fn("1e-7") == "0.0000001"  # positional, no exponent


def test_negative_zero_normalizes():
    assert fn("-0") == "0"
    assert fn("-0.0") == "0"


def test_non_finite_rejected():
    # JSON has no NaN/Infinity token; a native binary64 one must fail the commit.
    with pytest.raises(NumberError):
        format_number(float("nan"))
    with pytest.raises(NumberError):
        format_number(float("inf"))
