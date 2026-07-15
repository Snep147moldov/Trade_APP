"""Candle ingestion with pluggable providers.

Priority (mode "auto"): Twelve Data (REST+WS, intraday, all asset classes)
-> EODHD (daily candles incl. indices; intraday only on paid plans)
-> OANDA (legacy, forex/CFD only) -> deterministic simulator. Per-symbol,
per-timeframe fallback: whatever the active provider cannot serve silently
degrades to the next source, so every catalog instrument always has data.

All candles are dicts: {time (epoch s), open, high, low, close, volume,
complete}. The 40m timeframe is resampled from 5m everywhere.
"""

import math
import time
from typing import Any

import httpx
import numpy as np

from ..catalog import CATALOG, meta, pip_size, price_precision  # noqa: F401 (re-export)
from ..config import OANDA_HOSTS
from ..providers import eodhd
from ..providers import twelvedata as td

Candle = dict[str, Any]

# tf -> (oanda granularity, granularity seconds, resample factor)
_TF_MAP = {
    "1m": ("M1", 60, 1),
    "5m": ("M5", 300, 1),
    "15m": ("M15", 900, 1),
    "40m": ("M5", 300, 8),   # 8 x M5 -> 40m
    "1h": ("H1", 3600, 1),
    "4h": ("H4", 14400, 1),
    "1d": ("D", 86400, 1),
}

_oanda_names_cache: dict[str, Any] = {"ts": 0.0, "names": None}


def valid_instrument(symbol: str) -> bool:
    return symbol in CATALOG


# ---------------------------------------------------------------------------
# Simulated feed — deterministic pure function of the candle index, so every
# call (and later outcome evaluation) sees exactly the same series.
# ---------------------------------------------------------------------------

def _hash_noise(seed: float, idx: np.ndarray) -> np.ndarray:
    x = np.sin(idx * 12.9898 + seed * 78.233) * 43758.5453
    return x - np.floor(x)  # uniform-ish in [0, 1)


def _sim_mid(symbol: str, idx: np.ndarray) -> np.ndarray:
    base = meta(symbol)["base_price"]
    seed = float(sum(ord(c) for c in symbol))
    trend = (
        0.004 * np.sin(idx / 288 * 2 * math.pi + seed)
        + 0.0025 * np.sin(idx / 55 + seed * 2)
        + 0.0012 * np.sin(idx / 13 + seed * 3)
    )
    noise = (_hash_noise(seed, idx) - 0.5) * 0.0012
    noise = (noise + np.roll(noise, 1) + np.roll(noise, 2)) / 3
    return base * (1 + trend + noise)


def _simulated_candles(symbol: str, gran_sec: int, count: int) -> list[Candle]:
    now = int(time.time())
    last_idx = now // gran_sec
    idx = np.arange(last_idx - count, last_idx + 1, dtype=np.float64)

    close = _sim_mid(symbol, idx)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    seed = float(sum(ord(c) for c in symbol))
    base = meta(symbol)["base_price"]
    high = np.maximum(open_, close) + _hash_noise(seed + 7, idx) * 0.0006 * base
    low = np.minimum(open_, close) - _hash_noise(seed + 13, idx) * 0.0006 * base
    vol = (200 + _hash_noise(seed + 23, idx) * 800).astype(int)

    prec = price_precision(symbol)
    out: list[Candle] = []
    for i in range(1, len(idx)):  # skip idx[0] (only seeds the first open)
        t = int(idx[i]) * gran_sec
        out.append({
            "time": t,
            "open": round(float(open_[i]), prec),
            "high": round(float(high[i]), prec),
            "low": round(float(low[i]), prec),
            "close": round(float(close[i]), prec),
            "volume": int(vol[i]),
            "complete": t + gran_sec <= now,
        })
    return out


def sim_last_price(symbol: str) -> float:
    now = int(time.time())
    idx = np.array([now // 60], dtype=np.float64)
    return round(float(_sim_mid(symbol, idx)[0]), price_precision(symbol))


# ---------------------------------------------------------------------------
# OANDA feed (legacy)
# ---------------------------------------------------------------------------

def _headers(creds: dict[str, str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {creds['oanda_api_key']}",
        "Accept-Datetime-Format": "UNIX",
    }


def _host(creds: dict[str, str]) -> str:
    return OANDA_HOSTS.get(creds.get("oanda_env", "practice"), OANDA_HOSTS["practice"])


async def _oanda_candles(creds: dict[str, str], symbol: str,
                         granularity: str, count: int) -> list[Candle]:
    url = f"{_host(creds)}/v3/instruments/{symbol}/candles"
    params = {"granularity": granularity, "count": min(count, 5000), "price": "M"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=_headers(creds), params=params)
        r.raise_for_status()
        data = r.json()
    out: list[Candle] = []
    for c in data.get("candles", []):
        mid = c["mid"]
        out.append({
            "time": int(float(c["time"])),
            "open": float(mid["o"]),
            "high": float(mid["h"]),
            "low": float(mid["l"]),
            "close": float(mid["c"]),
            "volume": int(c["volume"]),
            "complete": bool(c["complete"]),
        })
    return out


async def _oanda_account_names(creds: dict[str, str]) -> set[str]:
    now = time.time()
    if _oanda_names_cache["names"] is not None and now - _oanda_names_cache["ts"] < 3600:
        return _oanda_names_cache["names"]
    url = f"{_host(creds)}/v3/accounts/{creds['oanda_account_id']}/instruments"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=_headers(creds))
            r.raise_for_status()
            data = r.json()
        names = {i["name"] for i in data.get("instruments", [])}
    except Exception:
        names = set()
    _oanda_names_cache.update(ts=now, names=names)
    return names


def _resample(candles: list[Candle], target_sec: int) -> list[Candle]:
    buckets: dict[int, list[Candle]] = {}
    for c in candles:
        key = (c["time"] // target_sec) * target_sec
        buckets.setdefault(key, []).append(c)
    out: list[Candle] = []
    for key in sorted(buckets):
        group = buckets[key]
        out.append({
            "time": key,
            "open": group[0]["open"],
            "high": max(g["high"] for g in group),
            "low": min(g["low"] for g in group),
            "close": group[-1]["close"],
            "volume": sum(g["volume"] for g in group),
            "complete": all(g["complete"] for g in group),
        })
    return out


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

async def _try_oanda(creds: dict, symbol: str, granularity: str,
                     raw_count: int) -> list[Candle] | None:
    if not creds.get("oanda_api_key") or not meta(symbol)["oanda"]:
        return None
    names = await _oanda_account_names(creds)
    if names and symbol not in names:
        return None
    try:
        return await _oanda_candles(creds, symbol, granularity, raw_count)
    except Exception:
        return None


async def get_candles(creds: dict[str, str], symbol: str, tf: str,
                      count: int = 200, live: bool = True) -> list[Candle]:
    """`live=False` marks bulk callers (screener/heatmap/rankings): they only
    use spare Twelve Data budget and fall back to cache/simulator instead of
    waiting for a rate-limit slot."""
    if tf not in _TF_MAP:
        raise ValueError(f"unsupported timeframe: {tf}")
    if symbol not in CATALOG:
        raise ValueError(f"unknown instrument: {symbol}")
    granularity, gran_sec, factor = _TF_MAP[tf]
    raw_count = count * factor + factor
    mode = creds.get("data_provider") or "auto"
    td_key = creds.get("twelvedata_api_key", "")

    eodhd_key = creds.get("eodhd_api_key", "")

    raw: list[Candle] | None = None
    if mode in ("auto", "twelvedata") and td_key:
        raw = await td.get_candles(td_key, symbol, tf, count, live=live)
    if raw is None and mode in ("auto", "eodhd") and eodhd_key:
        try:
            raw = await eodhd.get_candles(eodhd_key, symbol, tf, count, live=live)
        except Exception:
            raw = None
    if raw is None and mode in ("auto", "oanda"):
        raw = await _try_oanda(creds, symbol, granularity, raw_count)
    if raw is None:
        raw = _simulated_candles(symbol, gran_sec, raw_count)

    if factor > 1:
        raw = _resample(raw, gran_sec * factor)
    return raw[-count:]


def active_provider(creds: dict[str, str]) -> str:
    mode = creds.get("data_provider") or "auto"
    if mode == "simulation":
        return "simulation"
    if mode in ("auto", "twelvedata") and creds.get("twelvedata_api_key"):
        return "twelvedata"
    if mode in ("auto", "eodhd") and creds.get("eodhd_api_key"):
        return "eodhd"
    if mode in ("auto", "oanda") and creds.get("oanda_api_key"):
        return "oanda"
    return "simulation"
