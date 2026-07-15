"""Twelve Data integration: REST time_series/price + WebSocket price stream.

Catalog symbols (BASE_QUOTE) map to Twelve Data notation; symbols TD does not
serve (futures, unknown indices) are detected once, remembered, and the caller
falls back to another source. All REST traffic goes through a global
per-minute rate budget so screener/heatmap sweeps can never starve charts,
tracking or the watchlist.
"""

import asyncio
import calendar
import contextlib
import json
import os
import time
from typing import Any

import httpx

from ..catalog import CATALOG, meta
from ..config import TWELVEDATA_HOST, TWELVEDATA_WS

Candle = dict[str, Any]

# tf -> (td interval, seconds, resample factor). 40m = 8 x 5min.
TF_MAP = {
    "5m": ("5min", 300, 1),
    "15m": ("15min", 900, 1),
    "40m": ("5min", 300, 8),
    "1h": ("1h", 3600, 1),
    "4h": ("4h", 14400, 1),
    "1d": ("1day", 86400, 1),
}

# Indices/energy: candidate TD symbols tried in order; first that answers wins.
#
# Verified live against a Grow-plan key (2026-07-16): bare index tickers like
# SPX, NDX, DJI, DAX, UKX, CL, BRN, HG, NG on /time_series do NOT error — they
# silently match unrelated stocks/ETFs on random exchanges (e.g. "SPX" ->
# a 0.075 CAD TSXV penny stock, "DAX" -> a NASDAQ ETF, "CL"/"BRN"/"HG"/"NG" ->
# random NYSE common stocks). None of GDAXI/N225/AXJO/STOXX50E/FTSE resolve to
# real index data on /time_series even on Grow (404, or FTSE -> a Euronext
# ETF priced ~15 GBP, not the ~8000pt index) — TD's index reference list
# (/indices) is metadata-only here, not queryable via time_series on this
# plan. So: indices are NOT served by TD at all (fall through to EODHD daily
# / simulator); only WTI crude oil verified correct (type "Energy Resource").
# Do not add bare tickers back without checking meta.type first — see
# _looks_genuine() below for the safety net.
_SPECIAL: dict[str, list[str]] = {
    "WTICO_USD": ["WTI/USD"],
}

# Categories that must never legitimately resolve to a stock/ETF/ADR — a
# match against one of these types means TD's fuzzy symbol lookup collided
# with an unrelated ticker, not the instrument we asked for.
_FORBIDDEN_TYPES = {"Common Stock", "ETF", "American Depositary Receipt"}
_NON_EQUITY_CATEGORIES = {"forex", "metals", "energy", "indices", "crypto", "futures"}


def _looks_genuine(symbol: str, meta_block: dict) -> bool:
    m = meta(symbol)
    if not m or m["category"] not in _NON_EQUITY_CATEGORIES:
        return True
    return meta_block.get("type") not in _FORBIDDEN_TYPES

# symbol -> resolved TD symbol, or None when TD cannot serve it
_resolved: dict[str, str | None] = {}
_UNAVAILABLE_TTL = 6 * 3600
_unavailable_at: dict[str, float] = {}


def td_symbol_candidates(symbol: str) -> list[str]:
    m = meta(symbol)
    if not m:
        return []
    cat = m["category"]
    if symbol in _SPECIAL:
        return _SPECIAL[symbol]
    if cat == "forex" or cat == "metals" or cat == "crypto":
        base, quote = symbol.split("_", 1)
        return [f"{base}/{quote}"]
    if cat in ("stocks", "etf"):
        return [symbol.removesuffix("_USD")]
    return []  # futures and the rest — simulator only


def supported(symbol: str) -> bool:
    if not td_symbol_candidates(symbol):
        return False
    bad_at = _unavailable_at.get(symbol)
    if bad_at and time.time() - bad_at < _UNAVAILABLE_TTL:
        return False
    return True


def _mark_unavailable(symbol: str) -> None:
    _unavailable_at[symbol] = time.time()
    _resolved.pop(symbol, None)


# ---------------------------------------------------------------------------
# Global per-minute rate budget. "live" callers (charts, tracking, watchlist)
# wait for a slot; "cheap" callers (screener, heatmap, rankings) only take
# what is left over and otherwise report failure so the caller can fall back.
# ---------------------------------------------------------------------------

class RateBudget:
    def __init__(self, per_minute: int = 55):
        self.per_minute = per_minute
        self._stamps: list[float] = []
        self._lock = asyncio.Lock()

    def _prune(self) -> None:
        cutoff = time.time() - 60
        self._stamps = [s for s in self._stamps if s > cutoff]

    async def acquire(self, live: bool, timeout: float = 20.0) -> bool:
        deadline = time.time() + timeout
        while True:
            async with self._lock:
                self._prune()
                # cheap callers may not use the last 20% of the budget
                limit = self.per_minute if live else int(self.per_minute * 0.8)
                if len(self._stamps) < limit:
                    self._stamps.append(time.time())
                    return True
            if not live or time.time() > deadline:
                return False
            await asyncio.sleep(1.0)


# Free (basic) plan = 8 credits/min — default 7 keeps one in reserve.
# Paid plans: raise via TWELVEDATA_RPM env (e.g. 55 for Grow).
BUDGET = RateBudget(int(os.getenv("TWELVEDATA_RPM", "7")))

# (symbol, tf) -> {"ts": float, "candles": list}
_candle_cache: dict[tuple[str, str], dict[str, Any]] = {}


def _cache_fresh(symbol: str, tf: str, count: int) -> list[Candle] | None:
    entry = _candle_cache.get((symbol, tf))
    if not entry:
        return None
    gran_sec = TF_MAP[tf][1] * TF_MAP[tf][2]
    ttl = min(max(gran_sec / 2, 60), 300)
    if time.time() - entry["ts"] > ttl or len(entry["candles"]) < min(count, 50):
        return None
    return entry["candles"][-count:]


def cache_stale(symbol: str, tf: str, count: int) -> list[Candle] | None:
    entry = _candle_cache.get((symbol, tf))
    return entry["candles"][-count:] if entry else None


async def _request(client: httpx.AsyncClient, path: str, params: dict) -> dict | None:
    r = await client.get(f"{TWELVEDATA_HOST}{path}", params=params)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    return data


def _parse_values(values: list[dict], gran_sec: int) -> list[Candle]:
    now = time.time()
    out: list[Candle] = []
    for v in values:
        dt = v.get("datetime", "")
        try:
            fmt = "%Y-%m-%d" if len(dt) <= 10 else "%Y-%m-%d %H:%M:%S"
            t = int(calendar.timegm(time.strptime(dt, fmt)))
            out.append({
                "time": t,
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": int(float(v.get("volume") or 0)),
                "complete": t + gran_sec <= now,
            })
        except (ValueError, KeyError):
            continue
    out.sort(key=lambda c: c["time"])
    return out


async def get_candles(api_key: str, symbol: str, tf: str, count: int,
                      live: bool = True) -> list[Candle] | None:
    """Returns candles or None (unsupported symbol / no budget / API error).
    The caller decides the fallback. Resampling to 40m happens in candles.py."""
    if tf not in TF_MAP or not supported(symbol):
        return None
    interval, gran_sec, factor = TF_MAP[tf]
    raw_count = min(count * factor + factor, 5000)

    cached = _cache_fresh(symbol, tf, raw_count)
    if cached is not None:
        return cached

    if not await BUDGET.acquire(live=live):
        return cache_stale(symbol, tf, raw_count)  # stale beats nothing

    candidates = ([_resolved[symbol]] if _resolved.get(symbol)
                  else td_symbol_candidates(symbol))
    async with httpx.AsyncClient(timeout=25) as client:
        for td_sym in candidates:
            try:
                data = await _request(client, "/time_series", {
                    "symbol": td_sym, "interval": interval,
                    "outputsize": raw_count, "timezone": "UTC",
                    "apikey": api_key, "order": "asc",
                })
            except httpx.HTTPError:
                return cache_stale(symbol, tf, raw_count)
            if data and data.get("values"):
                if not _looks_genuine(symbol, data.get("meta", {})):
                    continue  # collided with an unrelated ticker — try next candidate
                _resolved[symbol] = td_sym
                candles = _parse_values(data["values"], gran_sec)
                if candles:
                    _candle_cache[(symbol, tf)] = {"ts": time.time(), "candles": candles}
                    return candles[-raw_count:]
    _mark_unavailable(symbol)
    return None


async def get_prices(api_key: str, symbols: list[str]) -> dict[str, float]:
    """Batch spot prices for catalog symbols TD serves. One credit per symbol."""
    usable = [s for s in symbols if supported(s)]
    if not usable or not await BUDGET.acquire(live=True):
        return {}
    td_map = {(_resolved.get(s) or td_symbol_candidates(s)[0]): s for s in usable}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await _request(client, "/price", {
                "symbol": ",".join(td_map), "apikey": api_key,
            })
    except httpx.HTTPError:
        return {}
    out: dict[str, float] = {}
    if not data:
        return out
    if len(td_map) == 1 and "price" in data:
        data = {next(iter(td_map)): data}
    for td_sym, payload in data.items():
        sym = td_map.get(td_sym)
        if sym and isinstance(payload, dict) and payload.get("price") is not None:
            try:
                out[sym] = float(payload["price"])
            except ValueError:
                continue
    return out


# ---------------------------------------------------------------------------
# WebSocket price stream -> shared quote cache (services.quotes.PRICE_CACHE)
# ---------------------------------------------------------------------------

class PriceStream:
    """Maintains one TD WebSocket subscription for the watchlist. Failures are
    silent (plan may not include WS) — REST polling remains the fallback."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._symbols: set[str] = set()
        self.connected = False

    def update(self, api_key: str, symbols: list[str], on_price) -> None:
        wanted = {s for s in symbols if supported(s) and meta(s)}
        if wanted == self._symbols and self._task and not self._task.done():
            return
        self._symbols = wanted
        if self._task:
            self._task.cancel()
        if api_key and wanted:
            self._task = asyncio.create_task(self._run(api_key, wanted, on_price))

    async def _run(self, api_key: str, symbols: set[str], on_price) -> None:
        try:
            import websockets
        except ImportError:
            return
        td_to_sym = {}
        for s in symbols:
            td = _resolved.get(s) or (td_symbol_candidates(s) or [None])[0]
            if td:
                td_to_sym[td] = s
        if not td_to_sym:
            return
        backoff = 5
        while True:
            try:
                async with websockets.connect(
                    f"{TWELVEDATA_WS}?apikey={api_key}", ping_interval=20
                ) as ws:
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "params": {"symbols": ",".join(td_to_sym)},
                    }))
                    self.connected = True
                    backoff = 5
                    async for raw in ws:
                        with contextlib.suppress(Exception):
                            msg = json.loads(raw)
                            if msg.get("event") == "price" and msg.get("price") is not None:
                                sym = td_to_sym.get(msg.get("symbol", ""))
                                if sym:
                                    on_price(sym, float(msg["price"]))
            except asyncio.CancelledError:
                self.connected = False
                raise
            except Exception:
                self.connected = False
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)


STREAM = PriceStream()


def catalog_coverage() -> dict[str, bool]:
    return {s: supported(s) for s in CATALOG}
