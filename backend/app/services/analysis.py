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

    # Scoring strictly on COMPLETED bars: the forming candle repaints, so a
    # signal taken on it could never be reproduced or fairly evaluated.
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

    components, weights, score, regime = score_components(
        snap, ai_news, ai_prediction, settings["min_adx"], settings["ai_weight"],
        factor_mults=factor_mults,
    )

    if score >= settings["min_score"]:
        direction = "BUY"
    elif score <= -settings["min_score"]:
        direction = "SELL"
    else:
        direction = "HOLD"

    # levels are always computed (for HOLD, along the leaning side) so the UI
    # can show what a trade *would* look like
    side = direction if direction != "HOLD" else ("BUY" if score >= 0 else "SELL")
    precision = price_precision(instrument)
    atr = snap["atr14"] or snap["close"] * 0.001
    levels = build_levels(side, snap["close"], atr,
                          settings["sl_atr_multiple"], settings["risk_reward"], precision)

    rates = await fx.eur_rates(db)
    risk = risk_manager.evaluate(
        db, instrument, timeframe, direction, score, snap, levels, settings,
        eur_per_quote=fx.eur_per_quote_unit(instrument, rates),
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
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "indicators": snap_public,
        "levels": levels,
        "risk": risk,
        "risk_reward": settings["risk_reward"],
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
