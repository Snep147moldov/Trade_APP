"""Economic calendar: rate decisions, CPI, NFP, inflation etc. with
high/medium/low impact — from the free ForexFactory weekly JSON feed.
Cached for 30 minutes. The scheduler warns 30 minutes before high-impact
events that touch currencies in the user's watchlist.
"""

import time
from datetime import datetime, timezone
from typing import Any

import httpx

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

_cache: dict[str, Any] = {"ts": 0.0, "events": None}

IMPACT_MAP = {"High": "high", "Medium": "medium", "Low": "low"}
IMPACT_RU = {"high": "высокое", "medium": "среднее", "low": "низкое"}


async def get_events(force: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    if not force and _cache["events"] is not None and now - _cache["ts"] < 1800:
        return _cache["events"]
    events: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(FF_URL, headers={"User-Agent": "Mozilla/5.0 (codnixy-ai-trade)"})
            r.raise_for_status()
            raw = r.json()
        for e in raw:
            try:
                ts = int(datetime.fromisoformat(e["date"]).timestamp())
            except (KeyError, ValueError):
                continue
            impact = IMPACT_MAP.get(e.get("impact", ""), "low")
            events.append({
                "title": e.get("title", ""),
                "currency": e.get("country", ""),
                "time": ts,
                "impact": impact,
                "forecast": e.get("forecast", ""),
                "previous": e.get("previous", ""),
            })
        events.sort(key=lambda x: x["time"])
        _cache.update(ts=now, events=events)
    except Exception:
        if _cache["events"] is not None:
            return _cache["events"]
        events = []
    return events


async def upcoming(within_minutes: int = 30,
                   min_impact: str = "high") -> list[dict[str, Any]]:
    order = {"low": 0, "medium": 1, "high": 2}
    threshold = order.get(min_impact, 2)
    now = int(datetime.now(timezone.utc).timestamp())
    events = await get_events()
    return [
        e for e in events
        if 0 <= e["time"] - now <= within_minutes * 60
        and order.get(e["impact"], 0) >= threshold
    ]


def format_alert(event: dict[str, Any]) -> str:
    mins = max(1, (event["time"] - int(time.time())) // 60)
    return (
        f"⚠️ <b>Через {mins} мин</b> — новость с высоким влиянием по "
        f"<b>{event['currency']}</b>:\n{event['title']}"
        + (f"\nПрогноз: {event['forecast']} · Пред.: {event['previous']}"
           if event.get("forecast") else "")
    )
