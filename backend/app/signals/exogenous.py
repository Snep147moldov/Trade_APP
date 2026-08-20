"""Факторы, НЕ выведенные из ценового ряда самого инструмента.

Восемь технических факторов формулы посчитаны по одному и тому же ряду цен, и
пять из них (trend, tsmom, kama_er, macd, roc) — просто разные способы измерить
одно движение. Сколько их ни складывай, новой информации не появится.

Здесь собрано то, что приходит извне цены инструмента:

  session_bias   время суток. Валюты систематически слабеют в СВОИ торговые
                 часы — эффект задокументирован на часовых данных (SNB WP
                 2011/04; Krohn, Journal of Finance 2024). Источник прямо
                 предупреждает, что эффект мал и в рознице ловится тяжело,
                 поэтому фактор обязан пройти проверку по IC до включения.

  dollar_align   насколько согласованно доллар движется против ВСЕХ мажоров.
                 Одна пара этого не видит: это информация из других рядов.
                 Ближайший аналог dollar factor из литературы по валютным
                 премиям (Lustig/Verdelhan).

  vol_regime     где текущий ATR относительно собственной истории. Не имеет
                 направления, поэтому НЕ складывается с остальными факторами —
                 это условие входа, а не прогноз.

Все функции возвращают значение в [-1, 1] по той же шкале, что и компоненты
`signals.engine`, чтобы их можно было честно сравнивать по IC.
"""

from datetime import datetime, timezone

import numpy as np

# Ориентировочные торговые окна в UTC (сдвигаются на час при переходе на
# летнее время; для фактора такой точности достаточно).
_SESSIONS = {
    "AUD": (21, 6),
    "NZD": (21, 6),
    "JPY": (0, 9),
    "EUR": (7, 16),
    "GBP": (7, 16),
    "CHF": (7, 16),
    "USD": (12, 21),
    "CAD": (12, 21),
}


def _active(hour: float, window: tuple[int, int]) -> bool:
    lo, hi = window
    return lo <= hour < hi if lo < hi else (hour >= lo or hour < hi)


def session_bias(instrument: str, ts: float) -> float:
    """+1 = час благоприятен для РОСТА пары, -1 = для падения.

    Механика из исследований: участники — нетто-покупатели иностранной валюты
    в свои часы, поэтому домашняя валюта в своей сессии слабеет. Для пары
    BASE/QUOTE активная сессия базовой валюты играет против пары, активная
    сессия котируемой — за неё. Когда обе сессии открыты (лондон-нью-йорк),
    эффекты гасят друг друга и фактор равен нулю.
    """
    parts = instrument.split("_")
    if len(parts) != 2:
        return 0.0
    base, quote = parts
    wb, wq = _SESSIONS.get(base), _SESSIONS.get(quote)
    if wb is None or wq is None:
        return 0.0
    h = datetime.fromtimestamp(ts, tz=timezone.utc).hour
    base_home = _active(h, wb)
    quote_home = _active(h, wq)
    if base_home == quote_home:
        return 0.0          # обе или ни одной — сигнала нет
    return -1.0 if base_home else 1.0


def vol_regime(atr: np.ndarray, i: int, lookback: int = 200) -> float:
    """Где текущий ATR внутри собственного распределения: -1 = аномально тихо,
    +1 = аномально бурно, 0 = обычно.

    НЕ направленный фактор: сам по себе ничего не предсказывает о знаке
    движения. Годится как условие входа — например, не торговать в верхнем
    хвосте, где стопы срывает новостными выбросами.
    """
    lo = max(0, i - lookback)
    window = atr[lo:i + 1]
    window = window[~np.isnan(window)]
    if len(window) < 30 or np.isnan(atr[i]):
        return 0.0
    pct = float((window < atr[i]).sum()) / len(window)
    return float(np.clip((pct - 0.5) * 2.0, -1.0, 1.0))


def dollar_align(returns_by_symbol: dict[str, float], instrument: str) -> float:
    """Насколько согласованно доллар движется против прочих мажоров.

    `returns_by_symbol` — доходность за последний бар, нормированная на ATR,
    по набору пар с USD. Считаем средний знак движения доллара по всем парам
    КРОМЕ разбираемой (иначе фактор частично повторит её собственную цену) и
    переводим в знак для этой пары.

    Возвращает 0 для инструментов без USD и когда данных меньше трёх пар.
    """
    parts = instrument.split("_")
    if len(parts) != 2 or "USD" not in parts:
        return 0.0
    usd_moves: list[float] = []
    for sym, r in returns_by_symbol.items():
        if sym == instrument:
            continue
        p = sym.split("_")
        if len(p) != 2 or "USD" not in p:
            continue
        # приводим к «движению доллара»: рост EUR/USD = падение доллара
        usd_moves.append(-r if p[1] == "USD" else r)
    if len(usd_moves) < 3:
        return 0.0
    usd_move = float(np.clip(np.mean(usd_moves), -1.0, 1.0))
    # знак для конкретной пары: USD базовая — движение доллара играет ЗА пару
    return usd_move if parts[0] == "USD" else -usd_move
