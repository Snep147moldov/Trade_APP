"""EODHD integration (secondary provider).

Free plan reality (detected live, not assumed): 20 requests/day, EOD-only —
intraday endpoints answer "Only EOD data allowed for free users". So this
module serves:

  - daily (1d) candles for forex / metals / stocks / ETF / crypto / indices
    (indices are a real win — Twelve Data free rarely carries them);
  - batched real-time quotes (up to 15 symbols per request);
  - intraday 5m/1h *if* the key's plan allows it (probed once per process;
    on the "Only EOD" answer intraday is marked blocked and never retried).

Aggressive caching keeps usage within tiny quotas: daily candles cache 6h,
a strict per-minute budget guards everything else.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..catalog import meta

HOST = "https://eodhd.com/api"
Candle = dict[str, Any]

# tf -> (eodhd intraday interval, seconds, resample factor); 1d uses /eod
TF_MAP = {
    "1m": ("1m", 60, 1),
    "5m": ("5m", 300, 1),
    "15m": ("5m", 300, 3),
    "40m": ("5m", 300, 8),
    "1h": ("1h", 3600, 1),
    "4h": ("1h", 3600, 4),
    "1d": (None, 86400, 1),
}

_INDEX_MAP = {
    "SPX500_USD": "GSPC.INDX",
    "NAS100_USD": "NDX.INDX",
    "US30_USD": "DJI.INDX",
    "DE30_EUR": "GDAXI.INDX",
    "UK100_GBP": "FTSE.INDX",
    "JP225_USD": "N225.INDX",
    "EU50_EUR": "STOXX50E.INDX",
    "AU200_AUD": "AXJO.INDX",
}

# probed at runtime: free plans cannot use /intraday at all
_intraday_blocked: bool | None = None

_candle_cache: dict[tuple[str, str], dict[str, Any]] = {}
_unavailable_at: dict[str, float] = {}
_UNAVAILABLE_TTL = 6 * 3600


class _Budget:
    """Tiny per-minute budget — free keys have only 20 calls/DAY, so the
    cache must do the real work; this just prevents accidental bursts."""

    def __init__(self, per_minute: int = 5):
        self.per_minute = per_minute
        self._stamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            cutoff = time.time() - 60
            self._stamps = [s for s in self._stamps if s > cutoff]
            if len(self._stamps) >= self.per_minute:
                return False
            self._stamps.append(time.time())
            return True


BUDGET = _Budget()


def eod_symbol(symbol: str) -> str | None:
    m = meta(symbol)
    if not m:
        return None
    cat = m["category"]
    if symbol in _INDEX_MAP:
        return _INDEX_MAP[symbol]
    if cat in ("forex", "metals"):
        return symbol.replace("_", "") + ".FOREX"
    if cat == "crypto":
        return symbol.replace("_", "-") + ".CC"
    if cat in ("stocks", "etf"):
        return symbol.removesuffix("_USD") + ".US"
    return None  # energy/futures — not served


def supported(symbol: str, tf: str) -> bool:
    if eod_symbol(symbol) is None or tf not in TF_MAP:
        return False
    if tf != "1d" and _intraday_blocked:
        return False
    bad = _unavailable_at.get(symbol)
    return not (bad and time.time() - bad < _UNAVAILABLE_TTL)


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> Any | None:
    r = await client.get(f"{HOST}{path}", params=params)
    # free plans answer 403 + "Only EOD data allowed..." on intraday endpoints
    if "Only EOD" in r.text[:120]:
        return "EOD_ONLY"
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _cache_get(symbol: str, tf: str, count: int) -> list[Candle] | None:
    entry = _candle_cache.get((symbol, tf))
    if not entry:
        return None
    ttl = 6 * 3600 if tf == "1d" else min(max(TF_MAP[tf][1] / 2, 60), 300)
    # never serve a shallower cache than requested (would truncate backtests)
    if time.time() - entry["ts"] > ttl or len(entry["candles"]) < count:
        return None
    return entry["candles"][-count:]


async def get_candles(api_key: str, symbol: str, tf: str, count: int,
                      live: bool = True) -> list[Candle] | None:
    global _intraday_blocked
    if not supported(symbol, tf):
        return None
    interval, gran_sec, factor = TF_MAP[tf]
    raw_count = count * factor + factor

    cached = _cache_get(symbol, tf, raw_count)
    if cached is not None:
        return cached
    if not await BUDGET.acquire():
        entry = _candle_cache.get((symbol, tf))
        return entry["candles"][-raw_count:] if entry else None  # stale > nothing

    sym = eod_symbol(symbol)
    now = time.time()
    async with httpx.AsyncClient(timeout=25) as client:
        if tf == "1d":
            since = (datetime.now(timezone.utc)
                     - timedelta(days=int(raw_count * 1.6) + 10)).strftime("%Y-%m-%d")
            data = await _get(client, f"/eod/{sym}", {
                "api_token": api_key, "fmt": "json", "order": "a", "from": since,
            })
            if not isinstance(data, list) or not data:
                _unavailable_at[symbol] = now
                return None
            out: list[Candle] = []
            for row in data:
                try:
                    t = int(datetime.strptime(row["date"], "%Y-%m-%d")
                            .replace(tzinfo=timezone.utc).timestamp())
                    out.append({
                        "time": t,
                        "open": float(row["open"]), "high": float(row["high"]),
                        "low": float(row["low"]), "close": float(row["close"]),
                        "volume": int(row.get("volume") or 0),
                        "complete": t + 86400 <= now,
                    })
                except (KeyError, TypeError, ValueError):
                    continue
        else:
            frm = int(now - raw_count * gran_sec * 1.4)
            data = await _get(client, f"/intraday/{sym}", {
                "api_token": api_key, "fmt": "json",
                "interval": interval, "from": frm,
            })
            if data == "EOD_ONLY":
                _intraday_blocked = True
                return None
            if not isinstance(data, list) or not data:
                _unavailable_at[symbol] = now
                return None
            _intraday_blocked = False
            out = []
            for row in data:
                try:
                    t = int(row["timestamp"])
                    out.append({
                        "time": t,
                        "open": float(row["open"]), "high": float(row["high"]),
                        "low": float(row["low"]), "close": float(row["close"]),
                        "volume": int(row.get("volume") or 0),
                        "complete": t + gran_sec <= now,
                    })
                except (KeyError, TypeError, ValueError):
                    continue

    out.sort(key=lambda c: c["time"])
    if out:
        _candle_cache[(symbol, tf)] = {"ts": now, "candles": out}
    return out[-raw_count:] if out else None


async def get_prices(api_key: str, symbols: list[str]) -> dict[str, float]:
    """Batched real-time quotes: 1 request serves up to 15 symbols."""
    pairs = [(s, eod_symbol(s)) for s in symbols]
    pairs = [(s, e) for s, e in pairs if e][:15]
    if not pairs or not await BUDGET.acquire():
        return {}
    first = pairs[0][1]
    extra = ",".join(e for _, e in pairs[1:])
    params = {"api_token": api_key, "fmt": "json"}
    if extra:
        params["s"] = extra
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            data = await _get(client, f"/real-time/{first}", params)
    except httpx.HTTPError:
        return {}
    if data is None or data == "EOD_ONLY":
        return {}
    rows = data if isinstance(data, list) else [data]
    back = {e: s for s, e in pairs}
    out: dict[str, float] = {}
    for row in rows:
        try:
            sym = back.get(row.get("code", ""))
            close = row.get("close")
            if sym and close not in (None, "NA"):
                out[sym] = float(close)
        except (TypeError, ValueError):
            continue
    return out
