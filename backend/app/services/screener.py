"""Скринер рынка + тепловые карты.

Bulk candle access always goes through get_candles(live=False): fresh cache
or spare Twelve Data budget when available, simulator otherwise — a full
sweep can never starve charts or signal tracking of API credits.
Results are cached for 10 minutes per category.
"""

import asyncio
import os
import time
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from ..catalog import CATALOG, CATEGORIES, meta
from ..config import G8
from ..indicators import core as ind
from .candles import get_candles
from .runtime import get_app_config, get_credentials

_cache: dict[str, dict[str, Any]] = {}  # category -> {"ts", "rows"}
# Fresher sweeps when the Twelve Data plan allows it (Grow: 55/min -> 5 min
# cache); free keys keep the conservative 10 min.
_TTL = 300 if int(os.getenv("TWELVEDATA_RPM", "7") or 7) >= 30 else 600
_BARS = 130  # 1h bars: enough for EMA50/ADX/RSI + 5 days of history


async def _row(creds: dict, symbol: str, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        try:
            candles = await get_candles(creds, symbol, "1h", _BARS, live=False)
        except Exception:
            return None
    if len(candles) < 60:
        return None
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    vol = np.array([c["volume"] for c in candles], dtype=np.float64)

    price = float(close[-1])
    chg_24h = (price / float(close[-25]) - 1) * 100 if len(close) > 25 else 0.0
    chg_5d = (price / float(close[0]) - 1) * 100
    atr14 = ind.atr(high, low, close, 14)[-1]
    atr_pct = float(atr14) / price * 100 if price and not np.isnan(atr14) else 0.0
    rsi14 = ind.rsi(close, 14)[-1]
    adx14 = ind.adx(high, low, close, 14)[0][-1]
    ema20 = ind.ema(close, 20)[-1]
    ema50 = ind.ema(close, 50)[-1]
    trend = 0
    if not (np.isnan(ema20) or np.isnan(ema50)):
        trend = 1 if ema20 > ema50 else -1
    roc10 = ind.roc(close, 10)[-1]
    vol_avg = float(vol[-21:-1].mean()) if len(vol) > 21 else 0.0
    vol_ratio = float(vol[-1]) / vol_avg if vol_avg > 0 else 1.0
    hi20 = float(high[-21:-1].max())
    lo20 = float(low[-21:-1].min())
    breakout = 1 if price > hi20 else (-1 if price < lo20 else 0)
    er = ind.efficiency_ratio(close, 10)

    m = meta(symbol)
    return {
        "symbol": symbol,
        "name": m["name"],
        "category": m["category"],
        "price": round(price, 6),
        "chg_24h_pct": round(chg_24h, 2),
        "chg_5d_pct": round(chg_5d, 2),
        "atr_pct": round(atr_pct, 3),
        "rsi14": round(float(rsi14), 1) if not np.isnan(rsi14) else None,
        "adx14": round(float(adx14), 1) if not np.isnan(adx14) else None,
        "trend": trend,
        "roc10": round(float(roc10), 2) if not np.isnan(roc10) else None,
        "volume_ratio": round(vol_ratio, 2),
        "breakout": breakout,
        "efficiency": round(er, 2),
        # composite momentum rank: direction * strength
        "momentum_score": round(float(
            np.tanh(chg_24h / max(atr_pct, 0.1)) * 0.5
            + trend * 0.25 + np.tanh((er - 0.3) * 2) * 0.25), 3),
    }


async def scan(db: Session, category: str = "forex", force: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = _cache.get(category)
    if cached and not force and now - cached["ts"] < _TTL:
        return {"rows": cached["rows"], "cached_at": cached["ts"], "category": category}

    creds = get_credentials(db)
    if category == "watchlist":
        symbols = get_app_config(db)["watchlist"]
    else:
        symbols = [s for s, m in CATALOG.items() if m["category"] == category]
    symbols = symbols[:150]

    sem = asyncio.Semaphore(10)
    results = await asyncio.gather(*(_row(creds, s, sem) for s in symbols))
    rows = [r for r in results if r]
    rows.sort(key=lambda r: -abs(r["momentum_score"]))
    _cache[category] = {"ts": now, "rows": rows}
    return {"rows": rows, "cached_at": now, "category": category}


# ---------------------------------------------------------------------------
# Heatmaps: per-category performance grid + G8 currency-strength matrix
# ---------------------------------------------------------------------------

async def heatmap(db: Session) -> dict[str, Any]:
    cats_out = []
    for key, label in CATEGORIES:
        data = await scan(db, key)
        items = [{"symbol": r["symbol"], "name": r["name"],
                  "chg_pct": r["chg_24h_pct"], "atr_pct": r["atr_pct"],
                  "rsi14": r["rsi14"]}
                 for r in data["rows"]]
        items.sort(key=lambda x: -x["chg_pct"])
        cats_out.append({"key": key, "label": label, "items": items[:40]})

    forex = {r["symbol"]: r for r in (await scan(db, "forex"))["rows"]}
    strength: dict[str, list[float]] = {c: [] for c in G8}
    matrix: dict[str, dict[str, float]] = {c: {} for c in G8}
    for base in G8:
        for quote in G8:
            if base == quote:
                continue
            row = forex.get(f"{base}_{quote}")
            if row:
                chg = row["chg_24h_pct"]
                strength[base].append(chg)
                strength[quote].append(-chg)
                matrix[base][quote] = chg
    strength_out = {c: round(float(np.mean(v)), 3) if v else 0.0
                    for c, v in strength.items()}
    return {
        "categories": cats_out,
        "currency_strength": dict(sorted(strength_out.items(), key=lambda kv: -kv[1])),
        "matrix": matrix,
    }
