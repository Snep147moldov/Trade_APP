"""Instrument catalog: every tradeable symbol across all asset classes.

Symbols follow the BASE_QUOTE convention (AAPL_USD, XAU_USD, BTC_USD) so the
whole pipeline stays uniform. `oanda` marks symbols that exist as OANDA CFDs
(used when live credentials are set); everything else runs on the simulator.

Stocks (~190) and cryptocurrencies (~90) come from curated lists in
symbols.py; any ticker outside the lists can be registered at runtime as a
custom instrument (persisted in the DB via services.runtime).
"""

import math
import re

from .config import G8
from .symbols import CRYPTO, STOCKS

CATEGORIES = [
    ("forex", "Форекс"),
    ("metals", "Металлы"),
    ("indices", "Индексы"),
    ("energy", "Энергоносители"),
    ("futures", "Фьючерсы"),
    ("stocks", "Акции"),
    ("etf", "ETF"),
    ("crypto", "Криптовалюты"),
]

_CUSTOM_RE = re.compile(r"^[A-Z0-9.]{1,10}_USD$")

# symbol -> (name, pip, base_price, category, oanda-available)
_RAW: dict[str, tuple[str, float, float, str, bool]] = {
    # Металлы (OANDA CFD)
    "XAU_USD": ("Золото", 0.1, 2400.0, "metals", True),
    "XAG_USD": ("Серебро", 0.01, 29.0, "metals", True),
    "XPT_USD": ("Платина", 0.1, 980.0, "metals", True),
    "XPD_USD": ("Палладий", 0.1, 950.0, "metals", True),
    "XCU_USD": ("Медь", 0.001, 4.3, "metals", True),
    # Индексы (OANDA CFD)
    "SPX500_USD": ("S&P 500", 1.0, 5500.0, "indices", True),
    "NAS100_USD": ("NASDAQ 100", 1.0, 20000.0, "indices", True),
    "US30_USD": ("Dow Jones 30", 1.0, 40000.0, "indices", True),
    "DE30_EUR": ("DAX 40", 1.0, 18500.0, "indices", True),
    "UK100_GBP": ("FTSE 100", 1.0, 8200.0, "indices", True),
    "JP225_USD": ("Nikkei 225", 1.0, 39000.0, "indices", True),
    "EU50_EUR": ("EuroStoxx 50", 1.0, 4900.0, "indices", True),
    "AU200_AUD": ("ASX 200", 1.0, 7800.0, "indices", True),
    # Энергоносители (OANDA CFD)
    "WTICO_USD": ("Нефть WTI", 0.01, 78.0, "energy", True),
    "BCO_USD": ("Нефть Brent", 0.01, 82.0, "energy", True),
    "NATGAS_USD": ("Природный газ", 0.001, 2.8, "energy", True),
    # Фьючерсы (симуляция)
    "ES_USD": ("Фьючерс S&P 500 (ES)", 0.25, 5500.0, "futures", False),
    "NQ_USD": ("Фьючерс NASDAQ (NQ)", 0.25, 20000.0, "futures", False),
    "YM_USD": ("Фьючерс Dow (YM)", 1.0, 40000.0, "futures", False),
    "CL_USD": ("Фьючерс нефть WTI (CL)", 0.01, 78.0, "futures", False),
    "GC_USD": ("Фьючерс золото (GC)", 0.1, 2400.0, "futures", False),
    "ZN_USD": ("Фьючерс 10Y T-Note (ZN)", 0.01, 110.0, "futures", False),
    # ETF (симуляция)
    "SPY_USD": ("SPDR S&P 500", 0.01, 550.0, "etf", False),
    "QQQ_USD": ("Invesco QQQ", 0.01, 480.0, "etf", False),
    "GLD_USD": ("SPDR Gold Shares", 0.01, 220.0, "etf", False),
    "IWM_USD": ("iShares Russell 2000", 0.01, 220.0, "etf", False),
    "EEM_USD": ("iShares MSCI EM", 0.01, 43.0, "etf", False),
    "VTI_USD": ("Vanguard Total Market", 0.01, 270.0, "etf", False),
    "VOO_USD": ("Vanguard S&P 500", 0.01, 505.0, "etf", False),
    "TLT_USD": ("iShares 20+Y Treasury", 0.01, 92.0, "etf", False),
    "HYG_USD": ("iShares High Yield", 0.01, 77.0, "etf", False),
    "XLE_USD": ("Energy Select SPDR", 0.01, 92.0, "etf", False),
    "XLK_USD": ("Technology Select SPDR", 0.01, 220.0, "etf", False),
    "XLF_USD": ("Financial Select SPDR", 0.01, 42.0, "etf", False),
    "ARKK_USD": ("ARK Innovation", 0.01, 45.0, "etf", False),
    "SLV_USD": ("iShares Silver", 0.01, 26.0, "etf", False),
    "USO_USD": ("United States Oil", 0.01, 75.0, "etf", False),
    "IBIT_USD": ("iShares Bitcoin Trust", 0.01, 37.0, "etf", False),
}

# USD value of 1 unit of each G8 currency — derives any simulated forex cross.
USD_PER = {
    "USD": 1.0, "EUR": 1.0850, "GBP": 1.2700, "JPY": 1 / 155.0,
    "CHF": 1 / 0.8900, "AUD": 0.6650, "CAD": 1 / 1.3600, "NZD": 0.6100,
}


def auto_pip(price: float) -> float:
    """Price-scaled pip so risk math works from SHIB to BTC: ~4 orders of
    magnitude below the price (a 0.1% move is always tens of 'pips')."""
    if price <= 0:
        return 0.0001
    return 10.0 ** (math.floor(math.log10(price)) - 4)


def _entry(symbol: str, name: str, pip: float, price: float,
           category: str, oanda: bool, custom: bool = False) -> dict:
    return {
        "symbol": symbol, "name": name, "pip": pip,
        "base_price": price, "category": category, "oanda": oanda,
        "custom": custom,
    }


def _build() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for base in G8:
        for quote in G8:
            if base == quote:
                continue
            sym = f"{base}_{quote}"
            catalog[sym] = _entry(
                sym, f"{base}/{quote}",
                0.01 if quote == "JPY" else 0.0001,
                USD_PER[base] / USD_PER[quote], "forex", True,
            )
    for sym, (name, pip, price, cat, oanda) in _RAW.items():
        catalog[sym] = _entry(sym, name, pip, price, cat, oanda)
    for ticker, name, price in STOCKS:
        sym = f"{ticker}_USD"
        catalog.setdefault(sym, _entry(sym, name, auto_pip(price), price, "stocks", False))
    for ticker, name, price in CRYPTO:
        sym = f"{ticker}_USD"
        catalog.setdefault(sym, _entry(sym, name, auto_pip(price), price, "crypto", False))
    return catalog


CATALOG: dict[str, dict] = _build()


def normalize_symbol(raw: str) -> str:
    s = raw.upper().strip().replace("/", "_").replace("-", ".")
    if not s.endswith("_USD"):
        s = f"{s}_USD"
    return s


def register_custom(raw_symbol: str, name: str = "",
                    category: str = "stocks", price: float | None = None) -> dict:
    """Add an arbitrary user ticker (persisted separately by the caller).
    Deterministic synthetic price when none is given — it only seeds the
    simulator. Raises ValueError on a malformed symbol."""
    sym = normalize_symbol(raw_symbol)
    if not _CUSTOM_RE.match(sym):
        raise ValueError("тикер: 1–10 символов A-Z, 0-9 или точка")
    if sym in CATALOG:
        return CATALOG[sym]
    if category not in ("stocks", "crypto"):
        category = "stocks"
    if price is None or price <= 0:
        h = sum(ord(c) * (i + 7) for i, c in enumerate(sym))
        price = round(10 ** (0.7 + (h % 1000) / 1000 * 2.3), 2)  # ~5..1000
    ticker = sym.removesuffix("_USD")
    entry = _entry(sym, name.strip() or ticker, auto_pip(price), price,
                   category, False, custom=True)
    CATALOG[sym] = entry
    return entry


def meta(symbol: str) -> dict | None:
    return CATALOG.get(symbol)


def pip_size(symbol: str) -> float:
    m = CATALOG.get(symbol)
    if m:
        return m["pip"]
    return 0.01 if symbol.endswith("_JPY") else 0.0001


def price_precision(symbol: str) -> int:
    pip = pip_size(symbol)
    if pip >= 1:
        return 2  # indices/crypto still show cents
    return min(10, max(2, int(round(-math.log10(pip))) + 1))


def currencies_of(symbol: str) -> list[str]:
    """G8 currencies a symbol is sensitive to (for news/calendar matching)."""
    m = CATALOG.get(symbol)
    if m and m["category"] == "forex":
        return symbol.split("_")
    # non-forex instruments: quote currency (usually USD) dominates
    quote = symbol.split("_")[-1]
    return [quote] if quote in G8 else ["USD"]


def categorized() -> list[dict]:
    out = []
    for key, label in CATEGORIES:
        items = [
            {"symbol": m["symbol"], "name": m["name"], "custom": m.get("custom", False)}
            for m in CATALOG.values() if m["category"] == key
        ]
        items.sort(key=lambda x: x["symbol"])
        out.append({"key": key, "label": label, "instruments": items})
    return out
