"""Time-to-expiry convention: calendar time, since crypto trades around the clock."""

from datetime import datetime

SECONDS_PER_YEAR = 365 * 24 * 3600


def year_fraction(start: datetime, end: datetime) -> float:
    """Calendar seconds from ``start`` to ``end`` over a 365-day year."""
    return (end - start).total_seconds() / SECONDS_PER_YEAR
