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
from ..database import SessionLocal
from . import memory as memory_svc
from .alerts import evaluate_alerts
from .analysis import analyze
from .quotes import ensure_stream
from .runtime import get_app_config, get_credentials
from .telegram import format_signal, send_message, signal_keyboard
from .tracking import create_signal, evaluate_open_signals

_last_scan_ts = 0.0
_last_eval_ts = 0.0
_last_alerts_ts = 0.0
_last_memory_ts = 0.0
_last_confidence_ts = 0.0
# (instrument, tf) -> {"direction", "ts"} — no repeat pings while the engine
# keeps saying the same thing about the same instrument
_confidence_sent: dict[tuple[str, str], dict] = {}
_weekend_notice_date: str = ""

CONFIDENCE_TFS = ("15m", "1h", "4h")
CONFIDENCE_COOLDOWN = 3600  # even a re-flipped direction pings max 1x/hour

# autoscan skips 1m/5m: sub-15m signals are spread-dominated noise for this
# engine (SL ~1.5*ATR is a handful of pips) and burn the API budget
AUTOSCAN_TFS = ("15m", "1h", "4h", "1d")


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
    # autotrade rides the same scan: it needs approved signals even when the
    # user has not switched the visible autoscan on
    if not (cfg["autoscan_enabled"] or cfg["autotrade_enabled"]) or not cfg["watchlist"]:
        return
    if time.time() - _last_scan_ts < cfg["scan_interval_min"] * 60:
        return
    _last_scan_ts = time.time()

    creds = get_credentials(db)
    for instrument in cfg["watchlist"]:
        for tf in AUTOSCAN_TFS:
            try:
                result = await analyze(instrument, tf, db)
            except Exception:
                continue
            # autoscan is always conservative: aggressive mode's sub-threshold
            # entries are for the user's own hand, never for the robot
            if not result["risk"]["approved"] or result.get("below_threshold"):
                continue
            sig = create_signal(db, result)
            if cfg["telegram_enabled"]:
                rec = autotrade_order_count(cfg, result["confidence"] * 100)
                await send_message(
                    creds["telegram_bot_token"],
                    cfg["telegram_chat_id"],
                    format_signal(result, sig.id, recommended_orders=rec),
                    reply_markup=signal_keyboard(sig.id, recommended=rec),
                )
            try:
                await _maybe_autotrade(db, cfg, result, sig)
            except Exception:
                pass


def autotrade_order_count(cfg: dict, confidence_pct: float) -> int:
    """Сколько ордеров открыть по одному сигналу: 1 на пороге уверенности,
    +1 за каждые 8 п.п. сверх порога, максимум autotrade_orders_per_signal.
    Детерминированная лестница: 75% -> 1, 83% -> 2, 91% -> 3 (при пороге 75)."""
    cap = max(1, min(int(cfg.get("autotrade_orders_per_signal", 1)), 5))
    extra = int(max(0.0, confidence_pct - cfg["autotrade_min_confidence"]) // 8)
    return min(cap, 1 + extra)


async def _maybe_autotrade(db, cfg: dict, result: dict, sig) -> None:
    """Открыть позицию (или несколько) в MT5 по одобренному сигналу
    автосканера — только когда движок уверен: сигнал прошёл риск-менеджер,
    не ниже порога оценки (это уже отфильтровано выше) и уверенность >=
    autotrade_min_confidence. Чем выше уверенность, тем больше ордеров
    (лестница до autotrade_orders_per_signal), тейки ставятся ступенями:
    первый ордер фиксирует +1R, последний бежит дальше цели. SL/TP идут
    прямо в ордере, выход дальше ведёт брокер."""
    if not cfg["autotrade_enabled"]:
        return
    conf_pct = result["confidence"] * 100
    if conf_pct < cfg["autotrade_min_confidence"]:
        return

    from . import mt5 as mt5_svc
    from .candles import price_precision
    from .notify import deliver

    creds = get_credentials(db)
    if not mt5_svc.is_configured(creds):
        return
    channels = ["app"] + (["telegram"] if cfg["telegram_enabled"] else [])

    pos = await mt5_svc.positions(db)
    if not pos["ok"]:
        return
    symbol = mt5_svc.mt5_symbol(result["instrument"], creds["mt5_symbol_suffix"])
    free_slots = cfg["autotrade_max_positions"] - len(pos["positions"])
    if free_slots <= 0:
        return
    if any(p["symbol"] == symbol for p in pos["positions"]):
        return  # уже есть позиция по этому инструменту

    lv = result["levels"]
    n = min(autotrade_order_count(cfg, conf_pct), free_slots)
    tps = mt5_svc.scale_out_take_profits(
        result["direction"], lv["entry"], lv["stop_loss"], lv["take_profit"],
        n, price_precision(result["instrument"]))

    opened: list[str] = []
    error: str | None = None
    for i, tp in enumerate(tps, start=1):
        tag = f" {i}/{len(tps)}" if len(tps) > 1 else ""
        r = await mt5_svc.place_order(
            db, result["instrument"], result["direction"], cfg["autotrade_lots"],
            lv["stop_loss"], tp, f"Codnixy auto #{sig.id}{tag}")
        if r["ok"]:
            opened.append(f"{r['lots']} лот, TP {tp}")
        else:
            error = r.get("error", "ошибка MT5")
            break

    if opened:
        await deliver(
            db, f"🤖 Автотрейд: {symbol} {result['direction']} ×{len(opened)}",
            f"Сигнал #{sig.id} ({result['timeframe']}, уверенность {int(conf_pct)}%): "
            f"открыто {len(opened)} ордер(а) — " + "; ".join(opened)
            + f". Общий SL {lv['stop_loss']}."
            + (f" Ордер {len(opened) + 1} отклонён: {error}" if error else ""),
            channels, kind="mt5", instrument=result["instrument"], source="mt5")
    elif error:
        await deliver(
            db, f"⚠️ Автотрейд: ордер {symbol} отклонён",
            f"Сигнал #{sig.id}: {error}",
            channels, kind="mt5", instrument=result["instrument"], source="mt5")


async def _confidence_tick(db) -> None:
    """Пуш, когда движок УВЕРЕН по инструменту из «Избранного»: направление,
    оценка, цена, уровни, время — и из уведомления можно сразу перейти на
    график. Только подтверждённые сигналы (не ниже порога), дедупликация по
    направлению + часовой кулдаун."""
    global _last_confidence_ts
    # 10 мин: чаще нет смысла — свечной кэш живёт 5 мин, а бюджет Twelve Data
    # делится с графиками; плотный опрос замедлял весь интерфейс
    if time.time() - _last_confidence_ts < 600:
        return
    _last_confidence_ts = time.time()

    cfg = get_app_config(db)
    if not cfg.get("notify_signals_enabled", True) or not cfg["watchlist"]:
        return

    from .notify import deliver

    for instrument in cfg["watchlist"]:
        for tf in CONFIDENCE_TFS:
            try:
                r = await analyze(instrument, tf, db)
            except Exception:
                continue
            key = (instrument, tf)
            prev = _confidence_sent.get(key)
            confident = (r["direction"] in ("BUY", "SELL")
                         and not r.get("below_threshold")
                         and r["risk"]["approved"])
            if not confident:
                if prev and prev["direction"] != "HOLD":
                    _confidence_sent[key] = {"direction": "HOLD", "ts": time.time()}
                continue
            if prev and prev["direction"] == r["direction"] \
                    and time.time() - prev["ts"] < CONFIDENCE_COOLDOWN:
                continue
            _confidence_sent[key] = {"direction": r["direction"], "ts": time.time()}

            side = "ПОКУПКА 📈" if r["direction"] == "BUY" else "ПРОДАЖА 📉"
            now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC, %d.%m")
            lv = r["levels"]
            channels = ["app"] + (["telegram"] if cfg["telegram_enabled"] else [])
            await deliver(
                db,
                f"{instrument.replace('_', '/')} · {tf} — {side}",
                f"Движок уверен: оценка {r['score']:+.2f}, уверенность "
                f"{int(r['confidence'] * 100)}%, режим "
                f"{'тренд' if r['regime'] == 'trending' else 'флэт'}. "
                f"Цена {lv['entry']}, SL {lv['stop_loss']}, TP {lv['take_profit']}. "
                f"{now_utc}.",
                channels, kind="signal_confidence",
                instrument=instrument, source="engine")


_last_market_scan_ts = 0.0
_market_scan_offset = 0         # rotating window over the candidate list
MARKET_SCAN_INTERVAL = 1800     # вне избранного — раз в 30 минут
MARKET_SCAN_TF = "1h"
MARKET_SCAN_COOLDOWN = 4 * 3600  # один и тот же инструмент — максимум раз в 4ч
MARKET_SCAN_CATEGORIES = ("forex", "metals", "indices", "crypto")
# per pass only a small rotating batch: the Twelve Data budget is shared with
# charts/tracking — a full-catalog sweep would starve the UI for minutes
MARKET_SCAN_BATCH = 8


async def _market_scan_tick(db) -> None:
    """Пуш и по рынкам ВНЕ «Избранного»: раз в 30 минут проходим форекс,
    металлы, индексы и крипту (1h), и если движок уверен (сигнал одобрен
    риск-менеджером, не ниже порога) — отправляем уведомление с пометкой,
    что инструмент не в избранном."""
    global _last_market_scan_ts, _market_scan_offset
    if time.time() - _last_market_scan_ts < MARKET_SCAN_INTERVAL:
        return
    _last_market_scan_ts = time.time()

    cfg = get_app_config(db)
    if not cfg.get("notify_all_markets", True) \
            or not cfg.get("notify_signals_enabled", True):
        return

    from ..catalog import CATALOG
    from .notify import deliver

    watch = set(cfg["watchlist"])
    pool = [s for s, m in CATALOG.items()
            if m.get("category") in MARKET_SCAN_CATEGORIES and s not in watch]
    if not pool:
        return
    start = _market_scan_offset % len(pool)
    candidates = (pool + pool)[start:start + MARKET_SCAN_BATCH]
    _market_scan_offset = (start + MARKET_SCAN_BATCH) % len(pool)

    for instrument in candidates:
        try:
            r = await analyze(instrument, MARKET_SCAN_TF, db)
        except Exception:
            continue
        confident = (r["direction"] in ("BUY", "SELL")
                     and not r.get("below_threshold")
                     and r["risk"]["approved"])
        if not confident:
            continue
        key = (instrument, "scan")
        prev = _confidence_sent.get(key)
        if prev and prev["direction"] == r["direction"] \
                and time.time() - prev["ts"] < MARKET_SCAN_COOLDOWN:
            continue
        _confidence_sent[key] = {"direction": r["direction"], "ts": time.time()}

        # полноценный сигнал в базе: отслеживается как остальные, и по нему
        # можно купить прямо из Telegram кнопками ×1/×2/×3
        sig = create_signal(db, r)

        side = "ПОКУПКА 📈" if r["direction"] == "BUY" else "ПРОДАЖА 📉"
        lv = r["levels"]
        await deliver(
            db,
            f"🔭 Вне избранного: {instrument.replace('_', '/')} · {MARKET_SCAN_TF} — {side}",
            f"Сигнал #{sig.id}: оценка {r['score']:+.2f}, уверенность "
            f"{int(r['confidence'] * 100)}%. Цена {lv['entry']}, "
            f"SL {lv['stop_loss']}, TP {lv['take_profit']}. "
            f"Купить можно из Telegram; добавьте в «Избранное» для "
            f"автоскана/автотрейда.",
            ["app"], kind="signal_confidence",
            instrument=instrument, source="engine")
        if cfg["telegram_enabled"]:
            creds = get_credentials(db)
            rec = autotrade_order_count(cfg, r["confidence"] * 100)
            await send_message(
                creds["telegram_bot_token"], cfg["telegram_chat_id"],
                "🔭 <b>Вне избранного</b>\n"
                + format_signal(r, sig.id, recommended_orders=rec),
                reply_markup=signal_keyboard(sig.id, recommended=rec))


async def _weekend_tick(db) -> None:
    """Одно предупреждение в пятницу, ~за 3 часа до закрытия рынка."""
    global _weekend_notice_date
    from ..models import Signal as _Sig
    from .market import forex_minutes_to_close
    from .notify import deliver
    from sqlalchemy import select as _select

    now = datetime.now(timezone.utc)
    if now.weekday() != 4:  # Friday only
        return
    today = now.strftime("%Y-%m-%d")
    if _weekend_notice_date == today:
        return
    mins = forex_minutes_to_close()
    if mins is None or mins > 180:
        return
    _weekend_notice_date = today

    open_sigs = db.scalars(_select(_Sig).where(_Sig.status == "open")).all()
    cfg = get_app_config(db)
    channels = ["app"] + (["telegram"] if cfg["telegram_enabled"] else [])
    body = (f"Рынок закрывается в 21:00 UTC (через ~{mins/60:.1f} ч). "
            + (f"Открыто позиций: {len(open_sigs)} — воскресный гэп может "
               f"перескочить стоп-лосс; рассмотрите закрытие до конца сессии."
               if open_sigs else
               "Новые входы будут заблокированы незадолго до закрытия."))
    await deliver(db, "⏳ Пятница: рынок скоро закрывается", body,
                  channels, kind="market_close", source="market")


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
                await _confidence_tick(db)
            except Exception:
                pass
            try:
                await _market_scan_tick(db)
            except Exception:
                pass
            try:
                await _weekend_tick(db)
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
