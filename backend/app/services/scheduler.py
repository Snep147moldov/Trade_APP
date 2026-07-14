"""Background loops:
  - news scheduler: fires the AI pipeline at the configured UTC times (1-2x/day)
  - autoscan: periodically analyzes the watchlist, saves approved signals,
    pushes them to Telegram
  - outcome evaluation + smart SL/TP management: every minute
  - custom alerts: every minute
  - price stream supervision: keeps the Twelve Data WS subscribed to watchlist
  - AI memory maintenance: consolidation after enough closed trades + pruning
"""

import asyncio
import time
from datetime import datetime, timezone

from ..agents.news import latest_analysis, run_pipeline
from ..config import TIMEFRAMES
from ..database import SessionLocal
from . import memory as memory_svc
from .alerts import evaluate_alerts
from .analysis import analyze
from .quotes import ensure_stream
from .runtime import get_app_config, get_credentials
from .telegram import format_signal, send_message
from .tracking import create_signal, evaluate_open_signals

_last_scan_ts = 0.0
_last_eval_ts = 0.0
_last_alerts_ts = 0.0
_last_memory_ts = 0.0


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


async def _news_tick(db) -> None:
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        return
    cfg = get_app_config(db)
    now = datetime.now(timezone.utc)
    latest = latest_analysis(db)
    latest_at = _as_utc(latest.created_at) if latest else None

    for t in cfg["news_times"]:
        try:
            hh, mm = (int(x) for x in t.split(":"))
        except ValueError:
            continue
        scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now >= scheduled and (latest_at is None or latest_at < scheduled):
            await run_pipeline(db, creds["anthropic_api_key"], cfg["watchlist"])
            return  # one run per tick


async def _autoscan_tick(db) -> None:
    global _last_scan_ts
    cfg = get_app_config(db)
    if not cfg["autoscan_enabled"] or not cfg["watchlist"]:
        return
    if time.time() - _last_scan_ts < cfg["scan_interval_min"] * 60:
        return
    _last_scan_ts = time.time()

    creds = get_credentials(db)
    for instrument in cfg["watchlist"]:
        for tf in TIMEFRAMES:
            try:
                result = await analyze(instrument, tf, db)
            except Exception:
                continue
            if not result["risk"]["approved"]:
                continue
            sig = create_signal(db, result)
            if cfg["telegram_enabled"]:
                await send_message(
                    creds["telegram_bot_token"],
                    cfg["telegram_chat_id"],
                    format_signal(result, sig.id),
                )


async def _memory_tick(db) -> None:
    """Consolidate lessons when enough trades have closed; prune old reviews."""
    global _last_memory_ts
    if time.time() - _last_memory_ts < 1800:
        return
    _last_memory_ts = time.time()
    cfg = get_app_config(db)
    if not cfg["memory_enabled"]:
        return
    memory_svc.prune(db)
    creds = get_credentials(db)
    if creds["anthropic_api_key"]:
        await memory_svc.consolidate(db, creds["anthropic_api_key"])


async def run_forever() -> None:
    global _last_eval_ts, _last_alerts_ts
    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            try:
                ensure_stream(db)  # keep WS subscription in sync with watchlist
            except Exception:
                pass
            try:
                await _news_tick(db)
            except Exception:
                pass  # AI/network failures must not kill the loop
            try:
                await _autoscan_tick(db)
            except Exception:
                pass
            try:
                await _calendar_tick(db)
            except Exception:
                pass
            if time.time() - _last_eval_ts >= 60:
                _last_eval_ts = time.time()
                try:
                    await evaluate_open_signals(db)
                except Exception:
                    pass
            if time.time() - _last_alerts_ts >= 60:
                _last_alerts_ts = time.time()
                try:
                    await evaluate_alerts(db)
                except Exception:
                    pass
            try:
                await _memory_tick(db)
            except Exception:
                pass
        finally:
            db.close()


# --------------------------------------------------------------------------
# Calendar alerts: warn 30 min before high-impact news touching the watchlist
# --------------------------------------------------------------------------

_notified_events: set[str] = set()


async def _calendar_tick(db) -> None:
    from ..catalog import currencies_of
    from .calendar import format_alert, upcoming
    from .notify import deliver

    cfg = get_app_config(db)
    if not cfg["watchlist"]:
        return
    watch_ccy: set[str] = set()
    for sym in cfg["watchlist"]:
        watch_ccy.update(currencies_of(sym))

    for e in await upcoming(within_minutes=31, min_impact="high"):
        key = f"{e['time']}:{e['currency']}:{e['title']}"
        if key in _notified_events or e["currency"] not in watch_ccy:
            continue
        _notified_events.add(key)
        channels = ["app"] + (["telegram"] if cfg["telegram_enabled"] else [])
        await deliver(db, f"Скоро важная новость: {e['currency']}",
                      f"{e['title']} — через ~30 минут. Возможен всплеск "
                      f"волатильности по инструментам с {e['currency']}.",
                      channels, kind="calendar", source="calendar")
