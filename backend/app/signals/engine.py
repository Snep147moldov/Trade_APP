"""Deterministic confluence engine.

Every factor is normalized into [-1, +1] (positive = bullish), then combined
as a weighted sum. AI sentiment/prediction enter as two bounded terms whose
combined weight is capped (default 15%) — the decision stays formula-driven.

Factors and their academic grounding:
  trend      tanh((EMA20 - EMA50) / ATR)          — moving-average trend
  tsmom      tanh(ret_20 / (ATR * sqrt(20)))      — time-series momentum
             (Moskowitz, Ooi & Pedersen 2012, J. Financial Economics)
  kama_er    Kaufman Efficiency Ratio, signed      — trend quality
             (Kaufman, 'Smarter Trading', 1995)
  macd       tanh(2 * MACD_hist / ATR)            — momentum acceleration
  rsi        (RSI14 - 50) / 50                    — momentum bias (Wilder 1978)
  stoch      cross + position blend               — short-term rotation
  bollinger  0.5 - %B, scaled                     — mean-reversion pull
             (Bollinger 2001)
  roc        tanh(ROC10 / (2 * ATR%))             — rate of change
  htf_trend  tanh((EMA20 - EMA50) / ATR) on the   — higher-timeframe
             next-higher timeframe                  confirmation (optional)

Regime switch (deterministic): market counts as RANGING when ADX14 < min_adx
AND Hurst exponent < 0.55 (R/S method; Hurst 1951, Lo 1991 'Long-Term Memory
in Stock Market Prices'). In ranging mode trend-following weights are halved
and mean-reversion weights doubled; RSI and the stochastic position term flip
to contrarian overbought/oversold readings (range-trading logic), because
momentum-following RSI is only meaningful while the market trends.
"""

import math
from typing import Any

import numpy as np

from ..indicators import core as ind

BASE_WEIGHTS = {
    "trend": 0.16,
    "tsmom": 0.14,
    "kama_er": 0.13,
    "macd": 0.12,
    "rsi": 0.09,
    "stoch": 0.06,
    "bollinger": 0.10,
    "roc": 0.05,
    # higher-timeframe confirmation — dropped (weights renormalized) when the
    # caller cannot provide an HTF snapshot (e.g. the backtest)
    "htf_trend": 0.12,
    # AI terms — capped, split evenly between the two agents
    "ai_news": 0.075,
    "ai_prediction": 0.075,
}

TSMOM_LOOKBACK = 20
ER_PERIOD = 10
HURST_TREND_THRESHOLD = 0.55


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_indicators(candles: list[dict]) -> dict[str, Any]:
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    volume = np.array([c.get("volume", 0) for c in candles], dtype=np.float64)

    ema20 = ind.ema(close, 20)
    ema50 = ind.ema(close, 50)
    rsi14 = ind.rsi(close, 14)
    macd_line, macd_sig, macd_hist = ind.macd(close)
    bb_mid, bb_up, bb_lo, pct_b = ind.bollinger(close)
    atr14 = ind.atr(high, low, close, 14)
    stoch_k, stoch_d = ind.stochastic(high, low, close)
    adx14, plus_di, minus_di = ind.adx(high, low, close)
    roc10 = ind.roc(close, 10)
    hurst = ind.hurst_exponent(close, window=100)
    er = ind.efficiency_ratio(close, ER_PERIOD)
    vwap48 = ind.vwap(high, low, close, volume, 48)
    tenkan, kijun, span_a, span_b = ind.ichimoku(high, low)

    def last(arr):
        v = arr[-1]
        return None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

    ret_n = float(close[-1] - close[-1 - TSMOM_LOOKBACK]) if len(close) > TSMOM_LOOKBACK else 0.0
    er_sign = 1.0 if len(close) > ER_PERIOD and close[-1] >= close[-1 - ER_PERIOD] else -1.0

    def ser(arr, digits=6):
        return [None if math.isnan(v) else round(float(v), digits) for v in arr]

    return {
        "close": float(close[-1]),
        "ema20": last(ema20), "ema50": last(ema50),
        "rsi14": last(rsi14),
        "macd": last(macd_line), "macd_signal": last(macd_sig), "macd_hist": last(macd_hist),
        "bb_mid": last(bb_mid), "bb_upper": last(bb_up), "bb_lower": last(bb_lo), "pct_b": last(pct_b),
        "atr14": last(atr14),
        "stoch_k": last(stoch_k), "stoch_d": last(stoch_d),
        "adx14": last(adx14), "plus_di": last(plus_di), "minus_di": last(minus_di),
        "roc10": last(roc10),
        "vwap": last(vwap48),
        "hurst": round(hurst, 3),
        "efficiency_ratio": round(er, 3),
        "er_signed": round(er * er_sign, 3),
        "tsmom_return": ret_n,
        "series": {
            "ema20": ser(ema20), "ema50": ser(ema50),
            "bb_upper": ser(bb_up), "bb_mid": ser(bb_mid), "bb_lower": ser(bb_lo),
            "vwap": ser(vwap48),
            "rsi": ser(rsi14, 2),
            "macd": ser(macd_line), "macd_signal": ser(macd_sig),
            "macd_hist": ser(macd_hist),
            "stoch_k": ser(stoch_k, 2), "stoch_d": ser(stoch_d, 2),
            "atr": ser(atr14),
            "ichimoku_tenkan": ser(tenkan), "ichimoku_kijun": ser(kijun),
            "ichimoku_span_a": ser(span_a), "ichimoku_span_b": ser(span_b),
        },
    }


def score_components(snap: dict[str, Any], ai_news: float, ai_prediction: float,
                     min_adx: float, ai_weight: float = 0.15,
                     factor_mults: dict[str, float] | None = None,
                     htf_score: float | None = None,
                     ) -> tuple[dict[str, float], dict[str, float], float, str]:
    """Returns (components, weights_used, total_score, regime).

    ai_weight caps the combined contribution of both AI terms (0 disables AI
    entirely); technical weights are rescaled to fill the remainder.
    factor_mults (from AI memory, bounded ±15%) tilt weights toward factors
    with a proven hit-rate; final weights are re-normalized to sum to 1.
    htf_score (higher-timeframe trend in [-1, 1]) confirms or fights the
    signal; None removes the factor and renormalizes the remaining weights.
    """
    atr = snap["atr14"] or 1e-9
    close = snap["close"]

    # Regime detection: ADX (Wilder) + Hurst exponent (R/S). Deterministic;
    # decided up front because RSI/stochastic switch meaning with the regime.
    adx = snap["adx14"]
    hurst = snap.get("hurst", 0.5)
    ranging = adx is not None and adx < min_adx and hurst < HURST_TREND_THRESHOLD

    comp: dict[str, float] = {}
    comp["trend"] = math.tanh((snap["ema20"] - snap["ema50"]) / atr) if snap["ema20"] and snap["ema50"] else 0.0

    # Time-series momentum (Moskowitz/Ooi/Pedersen 2012): volatility-scaled
    # lookback return
    comp["tsmom"] = math.tanh(snap["tsmom_return"] / (atr * math.sqrt(TSMOM_LOOKBACK)))

    # Kaufman efficiency ratio, signed by direction of the net move
    comp["kama_er"] = _clip(snap["er_signed"])

    comp["macd"] = math.tanh(2.0 * snap["macd_hist"] / atr) if snap["macd_hist"] is not None else 0.0

    # RSI: momentum bias while trending; contrarian at the 30/70 extremes in a
    # range (overbought fades, oversold bounces) and silent in the middle.
    if snap["rsi14"] is not None:
        rsi = snap["rsi14"]
        if ranging:
            if rsi >= 70:
                comp["rsi"] = _clip(-(rsi - 70.0) / 30.0 * 1.5)
            elif rsi <= 30:
                comp["rsi"] = _clip((30.0 - rsi) / 30.0 * 1.5)
            else:
                comp["rsi"] = 0.0
        else:
            comp["rsi"] = _clip((rsi - 50.0) / 50.0)
    else:
        comp["rsi"] = 0.0

    if snap["stoch_k"] is not None and snap["stoch_d"] is not None:
        k = snap["stoch_k"]
        cross = (k - snap["stoch_d"]) / 25.0
        if ranging:
            # range logic: %K beyond 80/20 is a fade, middle is noise
            if k >= 80:
                position = -(k - 80.0) / 20.0
            elif k <= 20:
                position = (20.0 - k) / 20.0
            else:
                position = 0.0
        else:
            position = (k - 50.0) / 50.0
        comp["stoch"] = _clip(0.6 * cross + 0.4 * position)
    else:
        comp["stoch"] = 0.0

    # %B > 1 → price above upper band → bearish mean-reversion pull
    comp["bollinger"] = _clip(2.0 * (0.5 - snap["pct_b"])) if snap["pct_b"] is not None else 0.0

    atr_pct = atr / close * 100.0
    comp["roc"] = math.tanh(snap["roc10"] / (2.0 * atr_pct)) if snap["roc10"] is not None and atr_pct > 0 else 0.0

    if htf_score is not None:
        comp["htf_trend"] = _clip(htf_score)

    comp["ai_news"] = _clip(ai_news)
    comp["ai_prediction"] = _clip(ai_prediction)

    # Rescale: AI terms get exactly ai_weight combined, technicals the rest
    ai_weight = _clip(ai_weight, 0.0, 0.5)
    weights = dict(BASE_WEIGHTS)
    if htf_score is None:
        del weights["htf_trend"]
    tech_keys = [k for k in weights if not k.startswith("ai_")]
    tech_total = sum(weights[k] for k in tech_keys)
    for k in tech_keys:
        weights[k] = weights[k] / tech_total * (1.0 - ai_weight)
    weights["ai_news"] = ai_weight / 2
    weights["ai_prediction"] = ai_weight / 2

    # Ranging market -> halve trend-following weights, double mean reversion.
    if ranging:
        for k in ("trend", "tsmom", "kama_er", "macd", "roc", "htf_trend"):
            if k in weights:
                weights[k] *= 0.5
        weights["bollinger"] *= 2.0
        weights["stoch"] *= 1.5
    if factor_mults:
        for k in weights:
            weights[k] *= factor_mults.get(k, 1.0)
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    score = sum(weights[k] * comp[k] for k in comp)
    regime = "ranging" if ranging else "trending"
    return comp, weights, _clip(score), regime


def build_levels(direction: str, close: float, atr: float,
                 sl_mult: float, risk_reward: float, precision: int) -> dict[str, float]:
    sl_dist = sl_mult * atr
    tp_dist = sl_dist * risk_reward
    if direction == "BUY":
        sl, tp = close - sl_dist, close + tp_dist
    else:
        sl, tp = close + sl_dist, close - tp_dist
    return {
        "entry": round(close, precision),
        "stop_loss": round(sl, precision),
        "take_profit": round(tp, precision),
        "sl_distance": round(sl_dist, precision),
        "tp_distance": round(tp_dist, precision),
    }
