import asyncio
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents import assistant as ai_assistant
from ..agents.news import analysis_to_dict, latest_analysis, run_pipeline
from ..backtest import engine as backtest_engine
from ..catalog import CATALOG, CATEGORIES, categorized, currencies_of, meta, register_custom
from ..config import APP_NAME, TIMEFRAMES
from ..models import Alert, AiMemory, ApiUsage, Signal, User
from ..auth.deps import audit, current_user, get_db
from ..risk import calculator as risk_calculator
from ..risk import limits as risk_limits
from ..risk import monitor as risk_monitor
from ..services import alerts as alerts_svc
from ..services import fx
from ..services import journal as journal_svc
from ..services import memory as memory_svc
from ..services import mt5 as mt5_svc
from ..services import notify
from ..services import screener as screener_svc
from ..services.analysis import analyze
from ..services.calendar import get_events, upcoming
from ..services.candles import active_provider, get_candles, valid_instrument
from ..services.market import market_state
from ..services.quotes import ensure_stream, get_quotes
from ..services.runtime import (
    get_app_config,
    get_credentials,
    is_ai_enabled,
    is_simulated,
    mask,
    persist_custom_instrument,
    update_app_config,
    update_credentials,
)
from ..services.settings import get_settings, update_settings
from ..services.telegram import format_signal, send_message, signal_keyboard
from ..services.tracking import create_signal, evaluate_open_signals, signal_stats
from ..signals.engine import compute_indicators
from ..signals.patterns import detect as detect_patterns

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

_volatility_cache: dict = {"ts": 0.0, "ranking": []}


def _check(instrument: str, tf: str) -> None:
    if not valid_instrument(instrument):
        raise HTTPException(404, f"неизвестный инструмент {instrument}")
    if tf not in TIMEFRAMES:
        raise HTTPException(
            404, f"неизвестный таймфрейм {tf} ({', '.join(TIMEFRAMES)})")


# --------------------------------------------------------------------------
# Health / market / calendar
# --------------------------------------------------------------------------

@router.get("/health")
async def health(db: Session = Depends(get_db)):
    cfg = get_app_config(db)
    return {
        "status": "ok",
        "app": APP_NAME,
        "simulated_data": is_simulated(db),
        "provider": active_provider(get_credentials(db)),
        "ai_enabled": is_ai_enabled(db),
        "telegram_enabled": cfg["telegram_enabled"],
        "watchlist": cfg["watchlist"],
        "timeframes": list(TIMEFRAMES.keys()),
        "currency": "EUR",
    }


@router.get("/market")
async def market():
    return market_state()


@router.get("/calendar")
async def calendar(db: Session = Depends(get_db)):
    cfg = get_app_config(db)
    watch_ccy: set[str] = set()
    for sym in cfg["watchlist"]:
        watch_ccy.update(currencies_of(sym))
    now = int(datetime.now(timezone.utc).timestamp())
    events = [e for e in await get_events() if e["time"] >= now - 3600]
    for e in events:
        e["relevant"] = e["currency"] in watch_ccy
    alerts = [
        e for e in await upcoming(within_minutes=30, min_impact="high")
        if not watch_ccy or e["currency"] in watch_ccy
    ]
    return {"events": events[:40], "alerts": alerts}


# --------------------------------------------------------------------------
# Instruments: categories + smart groups + watchlist
# --------------------------------------------------------------------------

async def _volatility_ranking(creds: dict) -> list[dict]:
    now = time.time()
    if _volatility_cache["ranking"] and now - _volatility_cache["ts"] < 600:
        return _volatility_cache["ranking"]

    sem = asyncio.Semaphore(10)

    async def atr_pct(symbol: str) -> dict | None:
        async with sem:
            try:
                candles = await get_candles(creds, symbol, "15m", 60, live=False)
                snap = compute_indicators(candles)
                if snap["atr14"] and snap["close"]:
                    return {
                        "symbol": symbol,
                        "name": meta(symbol)["name"],
                        "atr_pct": round(snap["atr14"] / snap["close"] * 100, 3),
                    }
            except Exception:
                return None
        return None

    results = await asyncio.gather(*(atr_pct(s) for s in CATALOG))
    ranking = sorted((r for r in results if r), key=lambda x: x["atr_pct"], reverse=True)
    _volatility_cache.update(ts=now, ranking=ranking)
    return ranking


@router.get("/instruments")
async def instruments(db: Session = Depends(get_db)):
    creds = get_credentials(db)
    cfg = get_app_config(db)

    volatile = (await _volatility_ranking(creds))[:8]

    news = latest_analysis(db)
    ai_recommended = []
    if news:
        for sym, b in sorted(news.pair_biases.items(),
                             key=lambda kv: abs(kv[1].get("bias", 0)), reverse=True):
            if abs(b.get("bias", 0)) >= 0.1 and sym in CATALOG:
                ai_recommended.append({
                    "symbol": sym,
                    "name": meta(sym)["name"],
                    "bias": b["bias"],
                    "rationale": b.get("rationale", ""),
                })

    return {
        "categories": categorized(),
        "watchlist": cfg["watchlist"],
        "groups": {
            "volatile": volatile,
            "ai_recommended": ai_recommended[:8],
        },
    }


class CustomInstrument(BaseModel):
    symbol: str
    name: str = ""
    category: str = "stocks"  # stocks | crypto


@router.post("/instruments/custom")
async def add_custom_instrument(req: CustomInstrument, request: Request,
                                db: Session = Depends(get_db),
                                user: User = Depends(current_user)):
    try:
        entry = register_custom(req.symbol, req.name, req.category)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    persist_custom_instrument(db, entry)
    audit(db, request, user, "custom_instrument", f"{entry['symbol']} ({entry['category']})")
    return {"symbol": entry["symbol"], "name": entry["name"], "category": entry["category"]}


class WatchlistPatch(BaseModel):
    watchlist: list[str]


@router.put("/watchlist")
async def put_watchlist(patch: WatchlistPatch, request: Request,
                        db: Session = Depends(get_db),
                        user: User = Depends(current_user)):
    cleaned = []
    for p in patch.watchlist:
        p = p.upper().replace("/", "_").strip()
        if valid_instrument(p) and p not in cleaned:
            cleaned.append(p)
    cfg = update_app_config(db, {"watchlist": cleaned})
    audit(db, request, user, "watchlist_update", ", ".join(cleaned) or "(пусто)")
    return {"watchlist": cfg["watchlist"]}


# --------------------------------------------------------------------------
# Candles / analysis
# --------------------------------------------------------------------------

@router.get("/candles")
async def candles(instrument: str, tf: str = "15m", count: int = 200,
                  db: Session = Depends(get_db)):
    _check(instrument, tf)
    creds = get_credentials(db)
    return await get_candles(creds, instrument, tf, min(count, 500))


@router.get("/analysis")
async def analysis(instrument: str, tf: str = "15m", db: Session = Depends(get_db)):
    _check(instrument, tf)
    return await analyze(instrument, tf, db)


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    instrument: str
    timeframe: str = "15m"


@router.post("/signals")
async def generate_signal(req: GenerateRequest, request: Request,
                          db: Session = Depends(get_db),
                          user: User = Depends(current_user)):
    _check(req.instrument, req.timeframe)
    result = await analyze(req.instrument, req.timeframe, db)
    if not result["risk"]["approved"]:
        return {"created": False, "analysis": result}
    sig = create_signal(db, result)
    audit(db, request, user, "signal_create",
          f"#{sig.id} {req.instrument} {req.timeframe} {result['direction']}")

    cfg = get_app_config(db)
    creds = get_credentials(db)
    telegram_sent = False
    if cfg["telegram_enabled"]:
        from ..services.scheduler import autotrade_order_count
        rec = autotrade_order_count(cfg, result["confidence"] * 100)
        r = await send_message(
            creds["telegram_bot_token"], cfg["telegram_chat_id"],
            format_signal(result, sig.id, recommended_orders=rec),
            reply_markup=signal_keyboard(sig.id, recommended=rec),
        )
        telegram_sent = r["ok"]

    # зеркалирование: созданный сигнал сразу открывает сделку в MT5 (лестница
    # ордеров по уверенности, тейки ступенями); дальше tracking ведёт SL/выход
    mt5_mirror = None
    if cfg["mt5_mirror_enabled"] and mt5_svc.is_configured(creds):
        from ..services.candles import price_precision
        from ..services.scheduler import autotrade_order_count
        lv = result["levels"]
        n = autotrade_order_count(cfg, result["confidence"] * 100)
        lots = mt5_svc.signal_lots(cfg, req.instrument,
                                   result["risk"].get("units"))
        mt5_mirror = await mt5_svc.place_signal_orders(
            db, req.instrument, result["direction"], lots,
            lv["entry"], lv["stop_loss"], lv["take_profit"], n,
            price_precision(req.instrument), f"Codnixy #{sig.id}")
        if mt5_mirror["ok"]:
            audit(db, request, user, "mt5_trade",
                  f"mirror #{sig.id} {result['direction']} x{mt5_mirror['opened']} "
                  f"{mt5_mirror['symbol']}")
            notify.add_notification(
                db, f"MT5: сигнал #{sig.id} → {mt5_mirror['symbol']}",
                f"{result['direction']} ×{mt5_mirror['opened']} по "
                f"{mt5_mirror['lots']} лот · SL {lv['stop_loss']} · "
                f"TP {', '.join(str(t) for t in mt5_mirror['take_profits'])}",
                kind="mt5", instrument=req.instrument, source="mt5")
    return {"created": True, "signal_id": sig.id, "telegram_sent": telegram_sent,
            "mt5": mt5_mirror, "analysis": result}


@router.get("/signals")
def list_signals(limit: int = 100, db: Session = Depends(get_db)):
    settings = get_settings(db)
    rows = db.scalars(
        select(Signal).order_by(Signal.created_at.desc()).limit(min(limit, 500))
    ).all()
    return {
        "signals": [
            {
                "id": s.id,
                "instrument": s.instrument,
                "timeframe": s.timeframe,
                "direction": s.direction,
                "entry": s.entry,
                "stop_loss": s.stop_loss,
                "take_profit": s.take_profit,
                "risk_reward": s.risk_reward,
                "units": s.units,
                "risk_amount": s.risk_amount,
                "score": s.score,
                "confidence": s.confidence,
                "components": s.components,
                "status": s.status,
                "pnl_pips": s.pnl_pips,
                "pnl_money": s.pnl_money,
                "mt5_pnl": s.mt5_pnl,
                "mt5_orders": s.mt5_orders,
                "mt5_volume": s.mt5_volume,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "resolved_at": s.resolved_at.isoformat() if s.resolved_at else None,
            }
            for s in rows
        ],
        "stats": signal_stats(db, settings["account_equity"]),
    }


@router.post("/signals/evaluate")
async def evaluate_signals(db: Session = Depends(get_db)):
    resolved = await evaluate_open_signals(db)
    settings = get_settings(db)
    return {"resolved": resolved, "stats": signal_stats(db, settings["account_equity"])}


class SignalsClearRequest(BaseModel):
    ids: list[int] | None = None       # явный список сигналов
    older_than_days: int | None = None  # только старше N дней
    scope: str = "closed"              # closed (по умолчанию) | all
    instrument: str | None = None      # только по инструменту


@router.post("/signals/clear")
def clear_signals(req: SignalsClearRequest, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """Удаление истории сигналов: по списку id, по возрасту (дни), по
    инструменту; scope=closed трогает только закрытые, scope=all — вообще все.
    Удалённые сигналы исчезают из статистики и кривой капитала."""
    if req.scope not in ("closed", "all"):
        raise HTTPException(400, "scope: closed | all")
    q = select(Signal)
    if req.ids:
        q = q.where(Signal.id.in_(req.ids))
    if req.scope == "closed":
        q = q.where(Signal.status.in_(("hit_tp", "hit_sl", "expired")))
    if req.older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, req.older_than_days))
        q = q.where(Signal.created_at < cutoff.replace(tzinfo=None))
    if req.instrument:
        q = q.where(Signal.instrument == req.instrument.upper().replace("/", "_"))
    rows = db.scalars(q).all()
    for s in rows:
        db.delete(s)
    db.commit()
    audit(db, request, user, "signals_clear",
          f"{len(rows)} шт. (scope={req.scope}, days={req.older_than_days}, "
          f"ids={len(req.ids or [])})")
    settings = get_settings(db)
    return {"deleted": len(rows), "stats": signal_stats(db, settings["account_equity"])}


@router.delete("/signals/{signal_id}")
def delete_signal(signal_id: int, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    sig = db.get(Signal, signal_id)
    if sig is None:
        raise HTTPException(404, "сигнал не найден")
    db.delete(sig)
    db.commit()
    audit(db, request, user, "signal_delete", f"#{signal_id} {sig.instrument}")
    settings = get_settings(db)
    return {"ok": True, "stats": signal_stats(db, settings["account_equity"])}


# --------------------------------------------------------------------------
# News / AI pipeline
# --------------------------------------------------------------------------

@router.get("/news")
async def news(db: Session = Depends(get_db)):
    cfg = get_app_config(db)
    data = analysis_to_dict(latest_analysis(db))
    data["enabled"] = is_ai_enabled(db)
    data["news_times"] = cfg["news_times"]
    return data


@router.post("/news/run")
async def news_run(request: Request, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ")
    cfg = get_app_config(db)
    try:
        row = await run_pipeline(db, creds["anthropic_api_key"], cfg["watchlist"])
    except Exception as exc:
        raise HTTPException(502, f"ошибка ИИ-конвейера: {type(exc).__name__}")
    audit(db, request, user, "news_run")
    data = analysis_to_dict(row)
    data["enabled"] = True
    data["news_times"] = cfg["news_times"]
    return data


# --------------------------------------------------------------------------
# Strategy settings
# --------------------------------------------------------------------------

@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return get_settings(db)


class SettingsPatch(BaseModel):
    account_equity: float | None = None
    risk_per_trade_pct: float | None = None
    risk_reward: float | None = None
    sl_atr_multiple: float | None = None
    min_score: float | None = None
    min_adx: float | None = None
    max_open_per_pair: float | None = None
    cooldown_minutes: float | None = None
    ai_weight: float | None = None
    sizing_mode: str | None = None
    signal_mode: str | None = None
    leverage: float | None = None
    trailing_enabled: bool | None = None
    trailing_atr_mult: float | None = None
    breakeven_at_r: float | None = None
    partial_tp_enabled: bool | None = None
    partial_tp_at_r: float | None = None
    partial_tp_fraction: float | None = None
    max_daily_loss: float | None = None
    max_daily_losses: int | None = None
    max_drawdown_pct: float | None = None
    daily_profit_target: float | None = None
    max_weekly_loss: float | None = None
    max_monthly_loss: float | None = None
    max_open_risk_pct: float | None = None
    weekend_guard_min: float | None = None


@router.put("/settings")
def write_settings(patch: SettingsPatch, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    result = update_settings(db, data)
    memory_svc.update_user_style(db, result)  # память запоминает стиль
    audit(db, request, user, "settings_update", ", ".join(data.keys()))
    return result


# --------------------------------------------------------------------------
# Connections (API keys, Telegram, schedule) + usage
# --------------------------------------------------------------------------

@router.get("/config")
def read_config(db: Session = Depends(get_db)):
    creds = get_credentials(db)
    cfg = get_app_config(db)
    return {
        "twelvedata_api_key": mask(creds["twelvedata_api_key"]),
        "eodhd_api_key": mask(creds["eodhd_api_key"]),
        "data_provider": cfg["data_provider"],
        "active_provider": active_provider(creds),
        "oanda_api_key": mask(creds["oanda_api_key"]),
        "oanda_account_id": creds["oanda_account_id"],
        "oanda_env": creds["oanda_env"],
        "anthropic_api_key": mask(creds["anthropic_api_key"]),
        "telegram_bot_token": mask(creds["telegram_bot_token"]),
        "telegram_chat_id": cfg["telegram_chat_id"],
        "telegram_enabled": cfg["telegram_enabled"],
        "news_times": cfg["news_times"],
        "autoscan_enabled": cfg["autoscan_enabled"],
        "scan_interval_min": cfg["scan_interval_min"],
        "stream_enabled": cfg["stream_enabled"],
        "memory_enabled": cfg["memory_enabled"],
        "notify_signals_enabled": cfg["notify_signals_enabled"],
        "notify_all_markets": cfg["notify_all_markets"],
        "alert_email": cfg["alert_email"],
        "smtp_host": creds["smtp_host"],
        "smtp_port": creds["smtp_port"],
        "smtp_user": creds["smtp_user"],
        "smtp_password": mask(creds["smtp_password"]),
        "smtp_from": creds["smtp_from"],
        "metaapi_token": mask(creds["metaapi_token"]),
        "mt5_login": creds["mt5_login"],
        "mt5_password": mask(creds["mt5_password"]),
        "mt5_server": creds["mt5_server"],
        "mt5_symbol_suffix": creds["mt5_symbol_suffix"],
        "mt5_account_id": creds["mt5_account_id"],
        "autotrade_enabled": cfg["autotrade_enabled"],
        "autotrade_min_confidence": cfg["autotrade_min_confidence"],
        "autotrade_max_positions": cfg["autotrade_max_positions"],
        "autotrade_lots": cfg["autotrade_lots"],
        "autotrade_orders_per_signal": cfg["autotrade_orders_per_signal"],
        "mt5_mirror_enabled": cfg["mt5_mirror_enabled"],
        "autotrade_risk_sizing": cfg["autotrade_risk_sizing"],
        "autotrade_max_lots": cfg["autotrade_max_lots"],
        "simulated_data": is_simulated(db),
        "ai_enabled": is_ai_enabled(db),
    }


class ConfigPatch(BaseModel):
    twelvedata_api_key: str | None = None
    eodhd_api_key: str | None = None
    data_provider: str | None = None
    oanda_api_key: str | None = None
    oanda_account_id: str | None = None
    oanda_env: str | None = None
    anthropic_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_enabled: bool | None = None
    news_times: list[str] | None = None
    autoscan_enabled: bool | None = None
    scan_interval_min: int | None = None
    stream_enabled: bool | None = None
    memory_enabled: bool | None = None
    notify_signals_enabled: bool | None = None
    notify_all_markets: bool | None = None
    alert_email: str | None = None
    smtp_host: str | None = None
    smtp_port: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    metaapi_token: str | None = None
    mt5_login: str | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_symbol_suffix: str | None = None
    autotrade_enabled: bool | None = None
    autotrade_min_confidence: int | None = None
    autotrade_max_positions: int | None = None
    autotrade_lots: float | None = None
    autotrade_orders_per_signal: int | None = None
    mt5_mirror_enabled: bool | None = None
    autotrade_risk_sizing: bool | None = None
    autotrade_max_lots: float | None = None


_CRED_KEYS = ("twelvedata_api_key", "eodhd_api_key", "oanda_api_key",
              "oanda_account_id", "oanda_env", "anthropic_api_key",
              "telegram_bot_token", "smtp_host", "smtp_port", "smtp_user",
              "smtp_password", "smtp_from", "metaapi_token", "mt5_login",
              "mt5_password", "mt5_server", "mt5_symbol_suffix")
_APP_KEYS = ("telegram_chat_id", "telegram_enabled", "news_times",
             "autoscan_enabled", "scan_interval_min", "data_provider",
             "stream_enabled", "memory_enabled", "notify_signals_enabled",
             "notify_all_markets",
             "alert_email", "autotrade_enabled", "autotrade_min_confidence",
             "autotrade_max_positions", "autotrade_lots",
             "autotrade_orders_per_signal", "mt5_mirror_enabled",
             "autotrade_risk_sizing", "autotrade_max_lots")


@router.put("/config")
def write_config(patch: ConfigPatch, request: Request,
                 db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    data = patch.model_dump(exclude_none=True)
    if "data_provider" in data and data["data_provider"] not in (
            "auto", "twelvedata", "eodhd", "oanda", "simulation"):
        raise HTTPException(400, "data_provider: auto | twelvedata | eodhd | oanda | simulation")
    cred_patch = {k: v for k, v in data.items()
                  if k in _CRED_KEYS and not str(v).startswith("•")}  # masked = unchanged
    app_patch = {k: v for k, v in data.items() if k in _APP_KEYS}
    if cred_patch:
        update_credentials(db, cred_patch)
    if app_patch:
        update_app_config(db, app_patch)
    ensure_stream(db)  # re-subscribe the price stream if provider/keys changed
    audit(db, request, user, "config_update", ", ".join(data.keys()))
    return read_config(db)


@router.post("/telegram/detect-chat")
async def telegram_detect_chat(db: Session = Depends(get_db)):
    """Находит chat_id по последнему сообщению боту и сохраняет его."""
    from ..services.telegram import detect_chat_id

    creds = get_credentials(db)
    r = await detect_chat_id(creds["telegram_bot_token"])
    if not r["ok"]:
        raise HTTPException(400, r.get("error", "не удалось определить chat_id"))
    update_app_config(db, {"telegram_chat_id": r["chat_id"]})
    return {"ok": True, "chat_id": r["chat_id"], "title": r.get("title", "")}


@router.post("/telegram/test")
async def telegram_test(db: Session = Depends(get_db)):
    creds = get_credentials(db)
    cfg = get_app_config(db)
    r = await send_message(
        creds["telegram_bot_token"], cfg["telegram_chat_id"],
        "✅ <b>Codnixy AI Trade</b> — тестовое сообщение. Подключение работает.",
    )
    if not r["ok"]:
        raise HTTPException(400, r.get("error", "ошибка отправки"))
    return {"ok": True}


# --------------------------------------------------------------------------
# MetaTrader 5 (MetaApi): connect account, status, positions, manual trade
# --------------------------------------------------------------------------

@router.get("/mt5/status")
async def mt5_status(db: Session = Depends(get_db)):
    return await mt5_svc.status(db)


@router.post("/mt5/connect")
async def mt5_connect(request: Request, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    r = await mt5_svc.connect(db)
    if not r.get("ok", False):
        raise HTTPException(400, r.get("error", "не удалось подключить MT5"))
    audit(db, request, user, "mt5_connect", str(r.get("login", "")))
    return r


@router.get("/mt5/positions")
async def mt5_positions(db: Session = Depends(get_db)):
    r = await mt5_svc.positions(db)
    if not r["ok"]:
        raise HTTPException(400, r.get("error", "ошибка MT5"))
    return r


class Mt5TradeRequest(BaseModel):
    instrument: str
    direction: str  # BUY | SELL
    lots: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    signal_id: int | None = None
    orders: int = 1  # 1..5 ордеров на один сигнал (тейки ступенями)


@router.post("/mt5/trade")
async def mt5_trade(req: Mt5TradeRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    _check(req.instrument, "15m")
    cfg = get_app_config(db)
    lots = req.lots if req.lots and req.lots > 0 else cfg["autotrade_lots"]
    n = max(1, min(req.orders, 5))
    base_comment = f"Codnixy #{req.signal_id}" if req.signal_id else "Codnixy manual"

    # несколько ордеров на сигнал: общий SL, тейки ступенями (+1R, цель, дальше)
    if n > 1 and req.stop_loss and req.take_profit:
        from ..services.candles import price_precision
        entry = (req.stop_loss + req.take_profit) / 2  # fallback без цены входа
        try:
            q = await get_quotes(db, [req.instrument])
            entry = q[req.instrument]["price"]
        except Exception:
            pass
        tps = mt5_svc.scale_out_take_profits(
            req.direction, entry, req.stop_loss, req.take_profit, n,
            price_precision(req.instrument))
    else:
        tps = [req.take_profit] * n

    results = []
    error: str | None = None
    for i, tp in enumerate(tps, start=1):
        tag = f" {i}/{len(tps)}" if len(tps) > 1 else ""
        r = await mt5_svc.place_order(db, req.instrument, req.direction, lots,
                                      req.stop_loss, tp, base_comment + tag)
        if not r["ok"]:
            error = r.get("error", "ордер отклонён")
            break
        results.append(r)

    if not results:
        raise HTTPException(400, error or "ордер отклонён")

    first = results[0]
    audit(db, request, user, "mt5_trade",
          f"{req.direction} {len(results)}x{first['lots']} lot {first['symbol']}")
    tp_txt = ", ".join(str(tp) for tp in tps[:len(results)]) if req.take_profit else "—"
    notify.add_notification(
        db, f"MT5: открыто {len(results)} позици(я/и) {first['symbol']}",
        f"{req.direction} {len(results)}×{first['lots']} лот · SL {req.stop_loss or '—'} · "
        f"TP {tp_txt}" + (f" · ордер {len(results) + 1} отклонён: {error}" if error else ""),
        kind="mt5", instrument=req.instrument, source="mt5")
    return {**first, "orders_opened": len(results), "orders_requested": n,
            "take_profits": tps[:len(results)],
            "position_ids": [r.get("position_id") for r in results],
            **({"partial_error": error} if error else {})}


class Mt5CloseRequest(BaseModel):
    position_id: str


@router.post("/mt5/close")
async def mt5_close(req: Mt5CloseRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    r = await mt5_svc.close_position(db, req.position_id)
    if not r["ok"]:
        raise HTTPException(400, r.get("error", "не удалось закрыть позицию"))
    audit(db, request, user, "mt5_close", req.position_id)
    return r


@router.get("/usage")
async def usage(db: Session = Depends(get_db)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start - timedelta(days=30)
    rates = await fx.eur_rates(db)

    def agg(since):
        row = db.execute(
            select(
                func.count(ApiUsage.id),
                func.coalesce(func.sum(ApiUsage.input_tokens), 0),
                func.coalesce(func.sum(ApiUsage.output_tokens), 0),
                func.coalesce(func.sum(ApiUsage.cost_usd), 0.0),
            ).where(ApiUsage.created_at >= since.replace(tzinfo=None))
        ).one()
        return {"calls": row[0], "input_tokens": int(row[1]),
                "output_tokens": int(row[2]), "cost_usd": round(float(row[3]), 4),
                "cost_eur": round(fx.usd_to_eur(float(row[3]), rates), 4)}

    recent = db.scalars(
        select(ApiUsage).order_by(ApiUsage.created_at.desc()).limit(20)
    ).all()
    return {
        "today": agg(today_start),
        "last_30d": agg(month_start),
        "eur_usd": round(1.0 / rates["USD"], 4) if rates.get("USD") else None,
        "recent": [
            {
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "model": u.model,
                "purpose": u.purpose,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cost_usd": u.cost_usd,
                "cost_eur": round(fx.usd_to_eur(u.cost_usd, rates), 4),
            }
            for u in recent
        ],
    }


# --------------------------------------------------------------------------
# Live quotes (WebSocket-поток / REST / симулятор — см. services/quotes.py)
# --------------------------------------------------------------------------

@router.get("/quotes")
async def quotes(symbols: str = "", db: Session = Depends(get_db)):
    wanted = [s for s in symbols.upper().replace("/", "_").split(",") if s][:40]
    if not wanted:
        wanted = get_app_config(db)["watchlist"][:40]
    data = await get_quotes(db, wanted)
    return {"quotes": data, "provider": active_provider(get_credentials(db))}


# --------------------------------------------------------------------------
# Chart patterns
# --------------------------------------------------------------------------

@router.get("/patterns")
async def patterns(instrument: str, tf: str = "1h", db: Session = Depends(get_db)):
    _check(instrument, tf)
    creds = get_credentials(db)
    candles = await get_candles(creds, instrument, tf, 200)
    return detect_patterns(candles)


# --------------------------------------------------------------------------
# Risk: monitor, limits, position-size calculator
# --------------------------------------------------------------------------

@router.get("/risk/monitor")
async def risk_monitor_endpoint(db: Session = Depends(get_db)):
    return await risk_monitor.portfolio_monitor(db)


@router.get("/risk/limits")
def risk_limits_endpoint(db: Session = Depends(get_db)):
    return risk_limits.day_state(db, get_settings(db))


class PositionSizeRequest(BaseModel):
    instrument: str
    entry: float
    stop_loss: float
    balance_eur: float | None = None   # default: account_equity
    risk_pct: float | None = None      # default: risk_per_trade_pct
    leverage: float | None = None
    commission_eur: float = 0.0
    spread_pips: float = 0.0
    risk_reward: float | None = None


@router.post("/risk/position-size")
async def position_size(req: PositionSizeRequest, db: Session = Depends(get_db)):
    if not valid_instrument(req.instrument):
        raise HTTPException(404, f"неизвестный инструмент {req.instrument}")
    settings = get_settings(db)
    creds = get_credentials(db)
    rates = await fx.eur_rates(db)
    atr = None
    try:
        candles = await get_candles(creds, req.instrument, "1h", 60)
        snap = compute_indicators(candles)
        atr = snap["atr14"]
    except Exception:
        pass
    return risk_calculator.position_size(
        instrument=req.instrument,
        balance_eur=req.balance_eur or settings["account_equity"],
        risk_pct=req.risk_pct or settings["risk_per_trade_pct"],
        entry=req.entry,
        stop_loss=req.stop_loss,
        leverage=req.leverage or settings["leverage"],
        commission_eur=req.commission_eur,
        spread_pips=req.spread_pips,
        atr=atr,
        eur_per_quote=fx.eur_per_quote_unit(req.instrument, rates),
        risk_reward=req.risk_reward or settings["risk_reward"],
    )


# --------------------------------------------------------------------------
# Journal
# --------------------------------------------------------------------------

@router.get("/journal/stats")
def journal_stats_endpoint(db: Session = Depends(get_db)):
    return journal_svc.journal_stats(db, get_settings(db)["account_equity"])


class SignalPatch(BaseModel):
    strategy: str | None = None
    notes: str | None = None


@router.patch("/signals/{signal_id}")
def patch_signal(signal_id: int, patch: SignalPatch, request: Request,
                 db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    sig = db.get(Signal, signal_id)
    if sig is None:
        raise HTTPException(404, "сигнал не найден")
    if patch.strategy is not None:
        sig.strategy = patch.strategy.strip()[:64]
    if patch.notes is not None:
        sig.notes = patch.notes.strip()[:4000]
    db.commit()
    audit(db, request, user, "signal_note", f"#{signal_id}")
    return {"ok": True, "id": sig.id, "strategy": sig.strategy, "notes": sig.notes}


@router.post("/journal/review")
async def journal_review(request: Request, db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ")
    try:
        result = await journal_svc.ai_review(
            db, creds["anthropic_api_key"], get_settings(db)["account_equity"])
    except Exception as exc:
        raise HTTPException(502, f"ошибка ИИ-разбора: {type(exc).__name__}")
    audit(db, request, user, "journal_review")
    return result


# --------------------------------------------------------------------------
# AI memory
# --------------------------------------------------------------------------

@router.get("/memory")
def memory_list(db: Session = Depends(get_db)):
    return {"memories": memory_svc.dump_all(db, 100),
            "enabled": get_app_config(db)["memory_enabled"]}


class MemoryNote(BaseModel):
    title: str
    content: str
    instrument: str = ""


@router.post("/memory")
def memory_add(req: MemoryNote, db: Session = Depends(get_db)):
    row = memory_svc.add_memory(db, "user_style", req.title, req.content,
                                instrument=req.instrument, importance=0.8,
                                tags=["user"])
    return memory_svc.memory_to_dict(row)


@router.delete("/memory/{memory_id}")
def memory_delete(memory_id: int, db: Session = Depends(get_db)):
    row = db.get(AiMemory, memory_id)
    if row is None:
        raise HTTPException(404, "запись не найдена")
    row.archived = 1
    db.commit()
    return {"ok": True}


@router.post("/memory/consolidate")
async def memory_consolidate(db: Session = Depends(get_db)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ")
    lessons = await memory_svc.consolidate(db, creds["anthropic_api_key"], force=True)
    return {"created": [memory_svc.memory_to_dict(l) for l in lessons],
            "closed_trades": memory_svc.closed_trades_count(db)}


# --------------------------------------------------------------------------
# AI assistant: chat + news intelligence per symbol
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    instrument: str = ""
    timeframe: str = "1h"


@router.post("/assistant/chat")
async def assistant_chat(req: ChatRequest, db: Session = Depends(get_db)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ — введите его в «Подключениях»")
    if req.instrument and not valid_instrument(req.instrument):
        raise HTTPException(404, f"неизвестный инструмент {req.instrument}")
    if req.timeframe not in TIMEFRAMES:
        req.timeframe = "1h"
    try:
        return await ai_assistant.chat(
            db, creds["anthropic_api_key"], req.message,
            req.history, req.instrument, req.timeframe)
    except Exception as exc:
        raise HTTPException(502, f"ошибка ассистента: {type(exc).__name__}")


class SymbolNewsRequest(BaseModel):
    instrument: str


@router.post("/assistant/news")
async def assistant_news(req: SymbolNewsRequest, db: Session = Depends(get_db)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ")
    if not valid_instrument(req.instrument):
        raise HTTPException(404, f"неизвестный инструмент {req.instrument}")
    try:
        return await ai_assistant.symbol_news(db, creds["anthropic_api_key"],
                                              req.instrument)
    except Exception as exc:
        raise HTTPException(502, f"ошибка новостного анализа: {type(exc).__name__}")


# --------------------------------------------------------------------------
# Alerts + notifications
# --------------------------------------------------------------------------

class AlertCreate(BaseModel):
    instrument: str
    timeframe: str = "1h"
    kind: str
    params: dict = {}
    channels: list[str] = ["app"]
    cooldown_min: int = 60
    note: str = ""


@router.get("/alerts")
def alerts_list(db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).order_by(Alert.created_at.desc())).all()
    return {"alerts": [alerts_svc.alert_to_dict(a) for a in rows],
            "kinds": list(alerts_svc.KINDS)}


@router.post("/alerts")
def alerts_create(req: AlertCreate, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    if not valid_instrument(req.instrument):
        raise HTTPException(404, f"неизвестный инструмент {req.instrument}")
    if req.kind not in alerts_svc.KINDS:
        raise HTTPException(400, f"неизвестный тип алерта {req.kind}")
    if req.timeframe not in TIMEFRAMES:
        raise HTTPException(400, "неизвестный таймфрейм")
    channels = [c for c in req.channels if c in ("app", "telegram", "email")] or ["app"]
    a = Alert(instrument=req.instrument, timeframe=req.timeframe, kind=req.kind,
              params=req.params, channels=channels,
              cooldown_min=max(1, min(req.cooldown_min, 24 * 60)),
              note=req.note[:200])
    db.add(a)
    db.commit()
    db.refresh(a)
    audit(db, request, user, "alert_create", f"{req.kind} {req.instrument}")
    return alerts_svc.alert_to_dict(a)


class AlertPatch(BaseModel):
    active: bool | None = None
    params: dict | None = None
    channels: list[str] | None = None
    cooldown_min: int | None = None
    note: str | None = None


@router.patch("/alerts/{alert_id}")
def alerts_patch(alert_id: int, patch: AlertPatch, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "алерт не найден")
    if patch.active is not None:
        a.active = 1 if patch.active else 0
    if patch.params is not None:
        a.params = patch.params
    if patch.channels is not None:
        a.channels = [c for c in patch.channels
                      if c in ("app", "telegram", "email")] or ["app"]
    if patch.cooldown_min is not None:
        a.cooldown_min = max(1, min(patch.cooldown_min, 24 * 60))
    if patch.note is not None:
        a.note = patch.note[:200]
    db.commit()
    return alerts_svc.alert_to_dict(a)


@router.delete("/alerts/{alert_id}")
def alerts_delete(alert_id: int, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "алерт не найден")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications_list(unread: bool = False, db: Session = Depends(get_db)):
    items = notify.list_notifications(db, 50, unread_only=unread)
    return {"notifications": items,
            "unread": sum(1 for n in items if not n["read"])}


class MarkReadRequest(BaseModel):
    ids: list[int] | None = None


@router.post("/notifications/read")
def notifications_read(req: MarkReadRequest, db: Session = Depends(get_db)):
    return {"marked": notify.mark_read(db, req.ids)}


# --------------------------------------------------------------------------
# Screener + heatmap
# --------------------------------------------------------------------------

@router.get("/screener")
async def screener(category: str = "forex", force: bool = False,
                   db: Session = Depends(get_db)):
    valid = {key for key, _ in CATEGORIES} | {"watchlist"}
    if category not in valid:
        raise HTTPException(400, f"категория: {', '.join(sorted(valid))}")
    return await screener_svc.scan(db, category, force=force)


@router.get("/heatmap")
async def heatmap(db: Session = Depends(get_db)):
    return await screener_svc.heatmap(db)


# --------------------------------------------------------------------------
# Backtesting
# --------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    instrument: str
    timeframe: str = "1h"
    bars: int = 1500
    initial_equity: float = 10000.0
    risk_per_trade_pct: float = 1.0
    min_score: float = 0.30
    min_adx: float = 18.0
    risk_reward: float = 1.8
    sl_atr_multiple: float = 1.5
    spread_pips: float = 1.0
    slippage_pips: float = 0.2
    commission_eur: float = 0.0
    cooldown_bars: int = 3
    walk_forward_folds: int = 0


@router.post("/backtest")
async def backtest(req: BacktestRequest, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    _check(req.instrument, req.timeframe)
    params = req.model_dump(exclude={"instrument", "timeframe", "walk_forward_folds"})
    try:
        result = await backtest_engine.run_backtest(
            db, req.instrument, req.timeframe, params, req.walk_forward_folds)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit(db, request, user, "backtest",
          f"{req.instrument} {req.timeframe} x{req.bars}")
    return result


@router.get("/backtest/runs")
def backtest_runs(db: Session = Depends(get_db)):
    return {"runs": backtest_engine.list_runs(db)}


@router.get("/backtest/runs/{run_id}")
def backtest_run_detail(run_id: int, db: Session = Depends(get_db)):
    from ..models import BacktestRun
    row = db.get(BacktestRun, run_id)
    if row is None:
        raise HTTPException(404, "бэктест не найден")
    return backtest_engine.run_to_dict(row, with_detail=True)


class BacktestAnalyzeRequest(BaseModel):
    run_id: int


@router.post("/backtest/analyze")
async def backtest_analyze(req: BacktestAnalyzeRequest, db: Session = Depends(get_db)):
    creds = get_credentials(db)
    if not creds["anthropic_api_key"]:
        raise HTTPException(400, "не задан Anthropic API ключ")
    try:
        return await backtest_engine.analyze_run(db, creds["anthropic_api_key"],
                                                 req.run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"ошибка анализа: {type(exc).__name__}")


# --------------------------------------------------------------------------
# Market depth: real volume profile + honest synthetic order book
# --------------------------------------------------------------------------

@router.get("/depth")
async def depth(instrument: str, tf: str = "15m", db: Session = Depends(get_db)):
    _check(instrument, tf)
    from ..services.depth import market_depth
    try:
        return await market_depth(db, instrument, tf)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
