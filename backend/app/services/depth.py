"""Стакан и глубина рынка.

Twelve Data (как и почти все розничные форекс-фиды) не отдаёт L2 — поэтому
панель честно разделяет два слоя:

  1. volume profile — РЕАЛЬНЫЕ данные: распределение объёма по ценовым
     уровням из последних свечей (+ доля объёма в растущих барах);
  2. синтетический стакан — ОЦЕНКА ликвидности: экспоненциальное затухание
     от середины, усиленное у пиков объёмного профиля и зон S/R.
     Детерминированный (хэш от символа и уровня), помечен synthetic=true.

Спред оценивается из волатильности (ATR) с полом в 0.5 пипса; стоимость
раунд-трипа считается в EUR для стандартного лота.
"""

import math
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from ..catalog import meta, pip_size, price_precision
from ..indicators import core as ind
from ..signals.patterns import detect as detect_patterns
from . import fx
from .candles import get_candles
from .quotes import get_quotes
from .runtime import get_credentials

PROFILE_BINS = 24
BOOK_LEVELS = 10


def _volume_profile(candles: list[dict], bins: int) -> list[dict[str, Any]]:
    hlc = np.array([(c["high"] + c["low"] + c["close"]) / 3 for c in candles])
    vol = np.array([c["volume"] for c in candles], dtype=np.float64)
    up = np.array([c["close"] >= c["open"] for c in candles])
    lo, hi = float(hlc.min()), float(hlc.max())
    if hi <= lo:
        return []
    edges = np.linspace(lo, hi, bins + 1)
    out = []
    for i in range(bins):
        mask = (hlc >= edges[i]) & (hlc < edges[i + 1] if i < bins - 1 else hlc <= edges[i + 1])
        v = float(vol[mask].sum())
        buy = float(vol[mask & up].sum())
        out.append({
            "price": round(float((edges[i] + edges[i + 1]) / 2), 6),
            "volume": int(v),
            "buy_frac": round(buy / v, 3) if v > 0 else 0.5,
        })
    return out


def _hash01(symbol: str, level: float, salt: int) -> float:
    x = math.sin(sum(ord(c) for c in symbol) * 12.9898
                 + level * 78.233 + salt * 37.719) * 43758.5453
    return x - math.floor(x)


def _synthetic_book(symbol: str, mid: float, spread: float, atr: float,
                    profile: list[dict], sr_prices: list[float],
                    prec: int) -> dict[str, list[dict]]:
    """Liquidity estimate: exp decay from mid, boosted near volume-profile
    peaks and S/R zones. Deterministic per (symbol, level)."""
    max_vol = max((p["volume"] for p in profile), default=1) or 1
    step = max(atr / 8, spread)

    def boost(price: float) -> float:
        b = 1.0
        for p in profile:
            if abs(p["price"] - price) < step:
                b += 1.5 * p["volume"] / max_vol
        for z in sr_prices:
            if abs(z - price) < step:
                b += 1.2
        return b

    def side(direction: int) -> list[dict]:
        rows = []
        for i in range(1, BOOK_LEVELS + 1):
            price = mid + direction * (spread / 2 + (i - 1) * step)
            base = math.exp(-0.28 * (i - 1)) * 10.0
            size = base * boost(price) * (0.7 + 0.6 * _hash01(symbol, price, i))
            rows.append({"price": round(price, prec), "size": round(size, 1)})
        return rows

    return {"bids": side(-1), "asks": side(+1)}


async def market_depth(db: Session, instrument: str, tf: str = "15m") -> dict[str, Any]:
    creds = get_credentials(db)
    candles = await get_candles(creds, instrument, tf, 200)
    if len(candles) < 40:
        raise ValueError("недостаточно свечей для профиля объёма")

    close = np.array([c["close"] for c in candles], dtype=np.float64)
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    atr_arr = ind.atr(high, low, close, 14)
    atr = float(atr_arr[-1]) if not np.isnan(atr_arr[-1]) else float(close[-1]) * 0.002

    quotes = await get_quotes(db, [instrument])
    mid = quotes.get(instrument, {}).get("price") or float(close[-1])

    pip = pip_size(instrument)
    prec = price_precision(instrument)
    # spread estimate: vol-scaled, floored at 0.5 pip (majors), capped at 5 pips
    spread = min(max(atr * 0.015, 0.5 * pip), 5 * pip)

    profile = _volume_profile(candles, PROFILE_BINS)
    large_levels = sorted(profile, key=lambda p: -p["volume"])[:3]

    patterns = detect_patterns(candles)
    sr_prices = [z["price"] for z in patterns["sr_zones"][:6]]

    book = _synthetic_book(instrument, mid, spread, atr, profile, sr_prices, prec)
    bid_total = sum(r["size"] for r in book["bids"])
    ask_total = sum(r["size"] for r in book["asks"])

    rates = await fx.eur_rates(db)
    eur_per_quote = fx.eur_per_quote_unit(instrument, rates)
    lot_cost_eur = 100_000 * spread * eur_per_quote  # round-trip cost, 1 lot

    m = meta(instrument)
    return {
        "instrument": instrument,
        "name": m["name"] if m else instrument,
        "timeframe": tf,
        "mid": round(mid, prec),
        "synthetic": True,  # провайдер не отдаёт реальный L2 — стакан оценочный
        "spread": {
            "price": round(spread, prec),
            "pips": round(spread / pip, 2),
            "lot_cost_eur": round(lot_cost_eur, 2),
            "atr_ratio_pct": round(spread / atr * 100, 1) if atr > 0 else None,
        },
        "book": book,
        "imbalance": round((bid_total - ask_total) / (bid_total + ask_total), 3)
        if bid_total + ask_total > 0 else 0.0,
        "volume_profile": profile,
        "large_levels": large_levels,
        "sr_prices": sr_prices,
    }
