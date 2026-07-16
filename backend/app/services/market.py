"""Market clock: forex trading sessions and open/closed state, all UTC-based.

Session hours are approximate UTC windows (they shift ±1h with DST):
Sydney 21-06, Tokyo 00-09, London 07-16, New York 12-21. The forex market as
a whole runs from Sunday ~21:00 UTC to Friday ~21:00 UTC.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

SESSIONS = [
    {"name": "Сидней", "open": 21, "close": 6},
    {"name": "Токио", "open": 0, "close": 9},
    {"name": "Лондон", "open": 7, "close": 16},
    {"name": "Нью-Йорк", "open": 12, "close": 21},
]


def _session_active(now: datetime, open_h: int, close_h: int) -> bool:
    h = now.hour + now.minute / 60
    if open_h < close_h:
        return open_h <= h < close_h
    return h >= open_h or h < close_h  # wraps midnight


def forex_minutes_to_close(now: datetime | None = None) -> float | None:
    """Minutes until the weekly forex close (Friday ~21:00 UTC). None when the
    market is already closed. Mondays return a large number — callers apply
    their own thresholds. Crypto trades 24/7 and must be exempted by caller."""
    now = now or datetime.now(timezone.utc)
    wd = now.weekday()
    h = now.hour + now.minute / 60
    if wd == 5 or (wd == 4 and h >= 21) or (wd == 6 and h < 21):
        return None  # weekend — closed
    days_to_friday = (4 - wd) % 7
    close = now.replace(hour=21, minute=0, second=0, microsecond=0)
    close = close + timedelta(days=days_to_friday)
    return max((close - now).total_seconds() / 60, 0.0)


def market_state() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    wd = now.weekday()  # Mon=0 .. Sun=6
    h = now.hour + now.minute / 60

    if wd == 5:  # Saturday — closed
        is_open = False
    elif wd == 4:  # Friday — closes ~21:00 UTC
        is_open = h < 21
    elif wd == 6:  # Sunday — opens ~21:00 UTC
        is_open = h >= 21
    else:
        is_open = True

    return {
        "now_utc": now.isoformat(),
        "epoch": int(now.timestamp()),
        "is_open": is_open,
        "sessions": [
            {
                "name": s["name"],
                "active": is_open and _session_active(now, s["open"], s["close"]),
                "open_utc": f"{s['open']:02d}:00",
                "close_utc": f"{s['close']:02d}:00",
            }
            for s in SESSIONS
        ],
    }
