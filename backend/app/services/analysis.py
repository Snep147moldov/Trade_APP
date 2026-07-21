"""Orchestrates one full analysis pass:
candles -> indicators -> stored AI vectors -> confluence score -> levels ->
risk gates. No AI calls happen here — the engine reads vectors saved by the
scheduled pipeline, so analysis is free to call as often as needed.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..agents.news import analysis_to_dict, latest_analysis, pair_sentiment
from ..risk import manager as risk_manager
from ..services.candles import get_candles, price_precision
from ..services.runtime import get_app_config, get_credentials
from ..signals.engine import build_levels, compute_indicators, score_components
from . import fx, memory
from .settings import get_settings


AI_STALENESS_HALF_LIFE_H = 12.0  # вес ИИ-векторов затухает вдвое каждые 12ч

# Higher-timeframe confirmation: each timeframe checks the trend one level up.
# 1d has no parent — the factor is dropped there (weights renormalize).
HTF_MAP = {"1m": "15m", "5m": "1h", "15m": "1h", "40m": "4h",
           "1h": "4h", "4h": "1d", "1d": None}


async def _htf_trend(creds: dict, instrument: str, timeframe: str) -> tuple[str | None, float | None]:
    """Trend of the next-higher timeframe as tanh((EMA20-EMA50)/ATR) on
    completed bars. Any failure returns None — the factor simply drops out."""
    import math

    htf = HTF_MAP.get(timeframe)
    if not htf:
        return None, None
    try:
        candles = await get_candles(creds, instrument, htf, 120)
        scoring = [c for c in candles if c["complete"]] or candles
        snap = compute_indicators(scoring)
        if snap["ema20"] and snap["ema50"] and snap["atr14"]:
            return htf, math.tanh((snap["ema20"] - snap["ema50"]) / snap["atr14"])
    except Exception:
        pass
    return htf, None


def _ai_decay(created_at_iso: str | None) -> float:
    """Stale news vectors must not push trades at full strength days later."""
    if not created_at_iso:
        return 0.0
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(created_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_h = max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0.0)
    except ValueError:
        return 1.0
    return 0.5 ** (age_h / AI_STALENESS_HALF_LIFE_H)


async def analyze(instrument: str, timeframe: str, db: Session) -> dict[str, Any]:
    settings = get_settings(db)
    creds = get_credentials(db)
    candles = await get_candles(creds, instrument, timeframe, 201)

    # CONFIRMED score: strictly on completed bars — the basis for tracked
    # signals (a forming candle repaints and can never be fairly evaluated).
    scoring = [c for c in candles if c["complete"]] or candles
    snap = compute_indicators(scoring)

    news = analysis_to_dict(latest_analysis(db))
    decay = _ai_decay(news["created_at"])
    ai_news = pair_sentiment(news["vector"], instrument) * decay
    stored_bias = news["pair_biases"].get(instrument, {})
    ai_prediction = stored_bias.get("bias", 0.0) * decay

    # накопленный опыт (память) детерминированно подстраивает веса факторов
    factor_mults = memory.factor_multipliers(db) \
        if get_app_config(db).get("memory_enabled", True) else None

    # подтверждение старшим таймфреймом: сигнал против старшего тренда
    # штрафуется, по тренду — усиливается (кэш свечей делает это дёшево)
    htf_tf, htf_score = await _htf_trend(creds, instrument, timeframe)

    components, weights, score, regime = score_components(
        snap, ai_news, ai_prediction, settings["min_adx"], settings["ai_weight"],
        factor_mults=factor_mults, htf_score=htf_score,
    )

    # LIVE score: same formula INCLUDING the forming candle. Moves in real
    # time with price; displayed as preliminary — it repaints by design.
    if len(candles) > len(scoring):
        live_snap = compute_indicators(candles)
        _, _, live_score, live_regime = score_components(
            live_snap, ai_news, ai_prediction,
            settings["min_adx"], settings["ai_weight"], factor_mults=factor_mults,
            htf_score=htf_score)
    else:
        live_score, live_regime = score, regime

    mode = settings.get("signal_mode", "conservative")
    below_threshold = abs(score) < settings["min_score"]
    if mode == "aggressive":
        # always pick a side; sub-threshold entries get half position size
        direction = "BUY" if score >= 0 else "SELL"
    elif score >= settings["min_score"]:
        direction = "BUY"
    elif score <= -settings["min_score"]:
        direction = "SELL"
    else:
        direction = "HOLD"

    # levels are anchored to the LIVE price — a signal created now enters at
    # the current market price, not at the close of the last finished bar
    side = direction if direction != "HOLD" else ("BUY" if score >= 0 else "SELL")
    precision = price_precision(instrument)
    atr = snap["atr14"] or snap["close"] * 0.001
    live_price = candles[-1]["close"] if candles else snap["close"]
    levels = build_levels(side, live_price, atr,
                          settings["sl_atr_multiple"], settings["risk_reward"], precision)

    rates = await fx.eur_rates(db)
    risk = risk_manager.evaluate(
        db, instrument, timeframe, direction, score, snap, levels, settings,
        eur_per_quote=fx.eur_per_quote_unit(instrument, rates),
        aggressive=(mode == "aggressive"), below_threshold=below_threshold,
    )

    last_candle = candles[-1] if candles else None
    snap_public = {k: v for k, v in snap.items() if k != "series"}
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "direction": direction,
        "score": round(score, 4),
        "confidence": round(min(1.0, abs(score) / 0.6), 2),
        "regime": regime,
        "mode": mode,
        "below_threshold": below_threshold,
        "live": {
            "score": round(live_score, 4),
            "direction": "BUY" if live_score >= 0 else "SELL",
            "price": live_price,
            "regime": live_regime,
        },
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "indicators": snap_public,
        "levels": levels,
        "risk": risk,
        "risk_reward": settings["risk_reward"],
        "htf": {
            "timeframe": htf_tf,
            "trend": round(htf_score, 3) if htf_score is not None else None,
        },
        "ai": {
            "news_pair_sentiment": round(ai_news, 3),
            "prediction": stored_bias or {"bias": 0.0, "confidence": 0.0, "rationale": ""},
            "analysis_time": news["created_at"],
            "staleness_decay": round(decay, 3),
        },
        "memory": {
            "enabled": factor_mults is not None,
            "factor_multipliers": {k: round(v, 3) for k, v in (factor_mults or {}).items()
                                   if abs(v - 1.0) > 1e-9},
        },
        "last_candle_time": last_candle["time"] if last_candle else None,
        "overlays": snap["series"],
        "candles": candles,
    }
