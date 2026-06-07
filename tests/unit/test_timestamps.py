"""Unit tests for the §12c lossless-or-reject timestamp normalizer."""

from __future__ import annotations

import pytest

from openproof.canonical.timestamps import TimestampError, normalize_ts


def test_three_fraction_digits_accepted():
    assert normalize_ts("2026-06-07T10:00:00.123Z") == "2026-06-07T10:00:00.123Z"


def test_fewer_fraction_digits_zero_padded():
    assert normalize_ts("2026-06-07T10:00:00.5Z") == "2026-06-07T10:00:00.500Z"
    assert normalize_ts("2026-06-07T10:00:00Z") == "2026-06-07T10:00:00.000Z"


def test_offset_converts_to_utc_byte_identically():
    # the same instant in +09:00 and its UTC form normalize to the same string
    assert normalize_ts("2026-06-07T09:30:00.000+09:00") == "2026-06-07T00:30:00.000Z"
    assert normalize_ts("2026-06-07T00:30:00.000Z") == "2026-06-07T00:30:00.000Z"


def test_sub_millisecond_precision_rejected():
    with pytest.raises(TimestampError):
        normalize_ts("2026-06-07T10:00:00.123456Z")  # microseconds → REJECT, never truncate


def test_leap_second_rejected():
    with pytest.raises(TimestampError):
        normalize_ts("2026-06-07T23:59:60.000Z")  # :60 → REJECT, never remap to :59.999


def test_unrecognized_rejected():
    with pytest.raises(TimestampError):
        normalize_ts("not a timestamp")
