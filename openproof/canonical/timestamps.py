"""The §12c lossless-or-reject native-timestamp normalizer (referenced wherever a native
``ts`` is serialized, e.g. the ``evidenceBoundary`` session window).

Parse RFC 3339 / ISO 8601, convert the SAME instant to UTC, and emit
``YYYY-MM-DDThh:mm:ss.mmmZ``: 0–2 fractional digits are zero-PADDED to three (lossless),
exactly three accepted, and MORE than three fractional digits or a leap-second ``:60`` are
REJECTED (never rounded/truncated/remapped — that would invent or collapse an instant).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

__all__ = ["TimestampError", "normalize_ts"]


class TimestampError(ValueError):
    """A native timestamp cannot be losslessly normalized (sub-ms precision or leap second)."""


_RFC3339 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|z|[+-]\d{2}:\d{2})$"
)


def normalize_ts(value: str) -> str:
    match = _RFC3339.match(value)
    if not match:
        raise TimestampError(f"unrecognized timestamp: {value!r}")
    year, month, day, hour, minute, second, frac, zone = match.groups()
    if second == "60":
        raise TimestampError(f"leap-second rejected (would invent/collide an instant): {value!r}")
    if frac is not None and len(frac) > 3:
        raise TimestampError(f"sub-millisecond precision rejected: {value!r}")
    millis = (frac or "").ljust(3, "0")  # 0–2 digits zero-padded to three (lossless)

    if zone in ("Z", "z"):
        offset = timedelta(0)
    else:
        sign = 1 if zone[0] == "+" else -1
        offset = sign * timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
    instant = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second),
                       tzinfo=timezone(offset)).astimezone(timezone.utc)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.") + millis + "Z"
