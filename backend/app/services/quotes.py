"""Shared live-quote cache.

Filled by (in priority order): the Twelve Data WebSocket stream, REST /price
polling for stale watchlist symbols, and the simulator for everything else.
The frontend polls /api/quotes; the risk monitor uses the same cache.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from ..catalog import CATALOG, price_precision
from ..providers import twelvedata as td
from .candles import active_provider, get_candles, sim_last_price
from .runtime import get_app_config, get_credentials

# symbol -> {"price": float, "ts": epoch, "source": "ws"|"rest"|"sim"|"candle"}
PRICE_CACHE: dict[str, dict[str, Any]] = {}

_FRESH_WS = 20.0
_FRESH_REST = 45.0


def push_price(symbol: str, price: float, source: str = "ws") -> None:
    PRICE_CACHE[symbol] = {"price": price, "ts": time.time(), "source": source}


def ensure_stream(db: Session) -> None:
    """(Re)subscribe the TD WebSocket to the current watchlist."""
    cfg = get_app_config(db)
    creds = get_credentials(db)
    if not cfg["stream_enabled"] or active_provider(creds) != "twelvedata":
        td.STREAM.update("", [], push_price)
        return
    td.STREAM.update(creds["twelvedata_api_key"], cfg["watchlist"],
                     lambda s, p: push_price(s, p, "ws"))


async def get_quotes(db: Session, symbols: list[str]) -> dict[str, dict[str, Any]]:
    creds = get_credentials(db)
    provider = active_provider(creds)
    now = time.time()
    out: dict[str, dict[str, Any]] = {}
    stale: list[str] = []

    from ..providers import eodhd

    for s in symbols:
        if s not in CATALOG:
            continue
        entry = PRICE_CACHE.get(s)
        max_age = _FRESH_WS if (entry and entry["source"] == "ws") else _FRESH_REST
        if entry and now - entry["ts"] < max_age:
            out[s] = entry
        elif provider == "twelvedata" and td.supported(s):
            stale.append(s)
        elif provider == "eodhd" and eodhd.eod_symbol(s):
            stale.append(s)
        else:
            price = sim_last_price(s) if provider == "simulation" else None
            if price is None:
                # oanda / unsupported: last candle close (cached upstream)
                try:
                    candles = await get_candles(creds, s, "5m", 2, live=True)
                    price = candles[-1]["close"] if candles else 0.0
                except Exception:
                    price = 0.0
                out[s] = {"price": price, "ts": now, "source": "candle"}
            else:
                out[s] = {"price": price, "ts": now, "source": "sim"}
            PRICE_CACHE[s] = out[s]

    if stale:
        if provider == "eodhd":
            fetched = await eodhd.get_prices(creds["eodhd_api_key"], stale[:15])
        else:
            fetched = await td.get_prices(creds["twelvedata_api_key"], stale[:30])
        for s, p in fetched.items():
            push_price(s, round(p, price_precision(s)), "rest")
            out[s] = PRICE_CACHE[s]
        for s in stale:
            if s not in out:  # REST failed — stale cache or candle close
                entry = PRICE_CACHE.get(s)
                if entry:
                    out[s] = entry
                else:
                    try:
                        candles = await get_candles(creds, s, "5m", 2)
                        if candles:
                            push_price(s, candles[-1]["close"], "candle")
                            out[s] = PRICE_CACHE[s]
                    except Exception:
                        continue
    return out


async def last_price(db: Session, symbol: str) -> float | None:
    q = await get_quotes(db, [symbol])
    return q.get(symbol, {}).get("price")
