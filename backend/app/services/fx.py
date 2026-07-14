"""EUR conversion: the whole app accounts in euros.

Live G8 rates come from the active data provider (EUR_x pairs are always in
the catalog); the static USD_PER table seeds a fallback when data is missing.
Rates are cached for 10 minutes — position sizing and P&L display do not need
tick-level FX precision.
"""

import time

from sqlalchemy.orm import Session

from ..catalog import USD_PER
from ..config import G8
from .candles import get_candles
from .runtime import get_credentials

_cache: dict = {"ts": 0.0, "rates": None}
_TTL = 600


def _static_rates() -> dict[str, float]:
    eur_usd = USD_PER["EUR"]
    return {c: USD_PER[c] / eur_usd for c in G8}  # EUR per 1 unit of c


async def eur_rates(db: Session) -> dict[str, float]:
    """{currency: EUR value of 1 unit}. EUR -> 1.0."""
    now = time.time()
    if _cache["rates"] and now - _cache["ts"] < _TTL:
        return _cache["rates"]
    creds = get_credentials(db)
    rates = _static_rates()
    for ccy in G8:
        if ccy == "EUR":
            continue
        try:
            candles = await get_candles(creds, f"EUR_{ccy}", "1h", 2)
            if candles and candles[-1]["close"] > 0:
                rates[ccy] = 1.0 / candles[-1]["close"]
        except Exception:
            continue  # keep static fallback for this currency
    rates["EUR"] = 1.0
    _cache.update(ts=now, rates=rates)
    return rates


def quote_currency(symbol: str) -> str:
    quote = symbol.split("_")[-1]
    return quote if quote in G8 else "USD"


def to_eur(amount: float, currency: str, rates: dict[str, float]) -> float:
    return amount * rates.get(currency, rates.get("USD", 0.9))


def usd_to_eur(amount: float, rates: dict[str, float]) -> float:
    return amount * rates.get("USD", 0.9)


def eur_per_quote_unit(symbol: str, rates: dict[str, float]) -> float:
    """EUR value of a 1.0 price move of 1 unit (price is quoted in the
    instrument's quote currency)."""
    return rates.get(quote_currency(symbol), rates.get("USD", 0.9))
