"""Unit tests for the §12c lossless numeric domain."""

from __future__ import annotations

import pytest

from openproof.canonical.numbers import NumberError, RawNumber, format_number


def fn(token: str) -> str:
    return format_number(RawNumber(token))


def test_integers_exact_arbitrary_precision():
    assert fn("9007199254740991") == "9007199254740991"  # 2^53 - 1
    assert fn("9007199254740992") == "9007199254740992"  # 2^53
    assert fn("9007199254740993") == "9007199254740993"  # 2^53 + 1, no binary64 collapse
    big = "123456789012345678901234567890"
    assert fn(big) == big


def test_2_53_neighbors_stay_distinct():
    assert fn("9007199254740992") != fn("9007199254740993")


def test_signed_and_zero_integers():
    assert fn("-5") == "-5"
    assert fn("0") == "0"
    assert fn("-0") == "0"


def test_non_integers_shortest_positional():
    assert fn("0.1") == "0.1"
    assert fn("1e-7") == "0.0000001"  # positional, never exponent
    assert fn("3.10") == "3.1"  # trailing-zero variant normalized, not rejected
    assert fn("0.540") == "0.54"


def test_large_exponent_float_token_is_positional():
    # an integral-valued float token (has an exponent) emits positionally, no exponent
    assert fn("1e16") == "10000000000000000"
    assert fn("1e21") == "1000000000000000000000"


def test_over_precision_rejected():
    with pytest.raises(NumberError):
        fn("1.0000000000000001")


def test_negative_zero_float_normalizes():
    assert fn("-0.0") == "0"
    assert format_number(-0.0) == "0"


def test_non_finite_rejected():
    with pytest.raises(NumberError):
        format_number(float("nan"))
    with pytest.raises(NumberError):
        format_number(float("inf"))
    with pytest.raises(NumberError):
        format_number(float("-inf"))


def test_native_int_and_float():
    assert format_number(42) == "42"
    assert format_number(2**70) == str(2**70)
    assert format_number(0.5) == "0.5"


def test_bool_rejected_as_number():
    with pytest.raises(NumberError):
        format_number(True)


def test_nonzero_underflow_to_zero_rejected():
    # a non-zero token that binary64 underflows to 0.0 must not silently become "0"
    with pytest.raises(NumberError):
        fn("1e-400")


def test_non_integer_token_with_integral_value_over_binary64_rejected():
    # 2^53+1 written as a float token cannot be represented exactly → reject, not collapse
    with pytest.raises(NumberError):
        fn("9007199254740993.0")


def test_unsupported_type_rejected():
    with pytest.raises(NumberError):
        format_number("123")  # a bare str is not a number input
    with pytest.raises(NumberError):
        format_number(None)
