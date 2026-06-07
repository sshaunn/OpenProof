"""Lossless number canonicalization (§12c, invariant ix).

The §12c canonical encoding pins a *lossless* numeric domain so the canonical
form can never silently alter or collapse a distinct source value:

  (a) integers      → their EXACT arbitrary-precision decimal literal
                      (no binary64 round-trip, so 2^53+1 never collides with 2^53);
  (b) non-integers  → interpreted as IEEE-754 binary64 and emitted as the SHORTEST
                      positional decimal that parses back to the identical binary64,
                      REJECTING a source token that carries more precision than
                      binary64 resolves (e.g. ``1.0000000000000001``);
  (c) negative zero → normalizes to ``0``;
      non-finite    → REJECTED (NaN / ±Infinity never emitted).

Source number tokens are preserved verbatim as :class:`RawNumber` (the JSONL parser
uses ``parse_int``/``parse_float`` = ``RawNumber``) so the lossless decision is made
on the original token, not on an already-lossy native float.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal

__all__ = ["RawNumber", "NumberError", "format_number"]


class NumberError(ValueError):
    """A source number cannot be canonically encoded (over-precision or non-finite)."""


@dataclass(frozen=True)
class RawNumber:
    """A JSON number token preserved verbatim from the source.

    Carries the original lexeme so the §12c lossless/over-precision decision is made
    against the source text, never against an already-collapsed native ``float``.
    """

    token: str


# A JSON number is an *integer* token iff it has no fraction and no exponent.
_INT_TOKEN = re.compile(r"^-?(?:0|[1-9][0-9]*)$")


def _decimal_to_positional(d: Decimal) -> str:
    """Render an exact ``Decimal`` as a positional decimal — no exponent, no
    superfluous trailing zeros or trailing ``.0``, sign preserved, ``-0`` → ``0``."""
    sign, digits, exp = d.as_tuple()
    digs = "".join(map(str, digits))
    if exp >= 0:
        s = digs + "0" * exp
    else:
        point = len(digs) + exp
        if point <= 0:
            s = "0." + "0" * (-point) + digs
        else:
            s = digs[:point] + "." + digs[point:]
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("", "0"):  # pragma: no cover - unreachable: callers guard f != 0
        return "0"
    return ("-" + s) if sign else s


def _format_binary64(f: float, exact: Decimal | None = None) -> str:
    """Shortest-round-trip positional form of a binary64, rejecting non-finite,
    underflow-to-zero, and genuine over-precision against ``exact`` (the source token)."""
    if not math.isfinite(f):
        raise NumberError(f"non-finite number rejected: {f!r}")
    if f == 0.0:  # also catches -0.0
        if exact is not None and exact != 0:
            raise NumberError(f"non-integer underflows to zero — rejected: {exact}")
        return "0"
    shortest = Decimal(repr(f))  # repr() is the shortest decimal that round-trips
    if exact is not None and exact != shortest:
        raise NumberError(f"over-precision non-integer rejected: {exact}")
    return _decimal_to_positional(shortest)


def format_number(value: RawNumber | int | float) -> str:
    """Canonical decimal string for a number, per the §12c lossless numeric domain.

    Accepts a source :class:`RawNumber` token, a native ``int`` (exact bignum), or a
    native ``float`` (binary64). ``bool`` is rejected — the encoder handles it as a
    JSON boolean before reaching here.
    """
    if isinstance(value, RawNumber):
        token = value.token
        if _INT_TOKEN.match(token):
            return str(int(token))  # exact arbitrary-precision integer
        return _format_binary64(float(token), exact=Decimal(token))
    if isinstance(value, bool):
        raise NumberError("bool is not a number (encode as a JSON boolean)")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_binary64(value)
    raise NumberError(f"unsupported number type: {type(value).__name__}")
