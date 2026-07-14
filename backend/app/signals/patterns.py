"""Автоматическое распознавание графических паттернов (чистый numpy).

Building blocks: fractal pivots -> clustered S/R zones -> fitted trendlines.
On top of those: channels, triangles, wedges, double tops/bottoms, head &
shoulders, flags/pennants, breakouts and false breakouts. Every detection is
deterministic and returns points the frontend can draw plus a Russian
explanation of the implication.
"""

from typing import Any

import numpy as np

from ..indicators import core as ind

PIVOT_K = 3
MAX_PATTERNS = 12


def _pivots(high: np.ndarray, low: np.ndarray, k: int = PIVOT_K):
    """Fractal pivots: bar i is a pivot high if high[i] is the max of i±k."""
    n = len(high)
    ph: list[int] = []
    pl: list[int] = []
    for i in range(k, n - k):
        if high[i] >= high[i - k:i + k + 1].max() and high[i] > high[i - 1]:
            ph.append(i)
        if low[i] <= low[i - k:i + k + 1].min() and low[i] < low[i - 1]:
            pl.append(i)
    return ph, pl


def _fit_line(xs: list[int], ys: np.ndarray) -> tuple[float, float, float]:
    """Least squares y = a*x + b over pivot points; returns (a, b, max_err)."""
    x = np.array(xs, dtype=np.float64)
    y = np.array([ys[i] for i in xs], dtype=np.float64)
    if len(x) < 2:
        return 0.0, float(y[0]) if len(y) else 0.0, 0.0
    a, b = np.polyfit(x, y, 1)
    err = float(np.abs(a * x + b - y).max())
    return float(a), float(b), err


def _pt(candles: list[dict], i: int, price: float) -> dict[str, Any]:
    return {"time": candles[i]["time"], "price": round(float(price), 6)}


def detect(candles: list[dict]) -> dict[str, Any]:
    if len(candles) < 60:
        return {"patterns": [], "sr_zones": [], "trendlines": [], "fibonacci": None}

    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    n = len(close)
    atr_arr = ind.atr(high, low, close, 14)
    atr = float(atr_arr[-1]) if not np.isnan(atr_arr[-1]) else float(close[-1]) * 0.002
    price = float(close[-1])

    ph, pl = _pivots(high, low)
    patterns: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ S/R
    zones = _sr_zones(candles, high, low, ph, pl, atr, price)

    # ------------------------------------------------------------ trendlines
    tl_out, upper, lower = _trendlines(candles, high, low, ph, pl, atr)

    # --------------------------------------------- channel / triangle / wedge
    if upper and lower:
        patterns.extend(_shape_from_lines(candles, upper, lower, atr, n))

    # -------------------------------------------------- double top / bottom
    patterns.extend(_double_extremes(candles, high, low, close, ph, pl, atr))

    # ---------------------------------------------------- head & shoulders
    patterns.extend(_head_shoulders(candles, high, low, close, ph, pl, atr))

    # ----------------------------------------------------- flags / pennants
    patterns.extend(_flags(candles, high, low, close, atr))

    # ------------------------------------------------ breakouts (vs S/R zones)
    patterns.extend(_breakouts(candles, close, zones, atr))

    patterns.sort(key=lambda p: -p["confidence"])
    fib = _fibonacci(candles, high, low)
    return {
        "patterns": patterns[:MAX_PATTERNS],
        "sr_zones": zones,
        "trendlines": tl_out,
        "fibonacci": fib,
    }


def _sr_zones(candles, high, low, ph, pl, atr, price) -> list[dict]:
    pts = [(i, float(high[i])) for i in ph] + [(i, float(low[i])) for i in pl]
    pts.sort(key=lambda t: t[1])
    zones: list[dict] = []
    cluster: list[tuple[int, float]] = []

    def flush():
        if len(cluster) >= 2:
            prices = [p for _, p in cluster]
            center = sum(prices) / len(prices)
            zones.append({
                "price": round(center, 6),
                "low": round(min(prices), 6),
                "high": round(max(prices), 6),
                "touches": len(cluster),
                "kind": "support" if center < price else "resistance",
                "last_touch": candles[max(i for i, _ in cluster)]["time"],
            })

    for i, p in pts:
        if cluster and p - cluster[-1][1] > 0.5 * atr:
            flush()
            cluster = []
        cluster.append((i, p))
    flush()
    zones.sort(key=lambda z: -z["touches"])
    return zones[:8]


def _trendlines(candles, high, low, ph, pl, atr):
    out: list[dict] = []
    upper = lower = None
    if len(ph) >= 2:
        xs = ph[-4:]
        a, b, err = _fit_line(xs, high)
        if err < 0.9 * atr:
            upper = (a, b, xs)
            out.append({
                "side": "resistance", "touches": len(xs),
                "points": [_pt(candles, xs[0], a * xs[0] + b),
                           _pt(candles, len(candles) - 1, a * (len(candles) - 1) + b)],
                "slope_per_bar": round(a, 8),
            })
    if len(pl) >= 2:
        xs = pl[-4:]
        a, b, err = _fit_line(xs, low)
        if err < 0.9 * atr:
            lower = (a, b, xs)
            out.append({
                "side": "support", "touches": len(xs),
                "points": [_pt(candles, xs[0], a * xs[0] + b),
                           _pt(candles, len(candles) - 1, a * (len(candles) - 1) + b)],
                "slope_per_bar": round(a, 8),
            })
    return out, upper, lower


def _shape_from_lines(candles, upper, lower, atr, n) -> list[dict]:
    (au, bu, xsu), (al, bl, xsl) = upper, lower
    flat = 0.05 * atr  # per-bar slope considered "flat"
    conv = (au * n + bu) - (al * n + bl) < (au * xsu[0] + bu) - (al * xsl[0] + bl)
    pts = [_pt(candles, min(xsu[0], xsl[0]),
               au * min(xsu[0], xsl[0]) + bu),
           _pt(candles, n - 1, au * (n - 1) + bu),
           _pt(candles, min(xsu[0], xsl[0]),
               al * min(xsu[0], xsl[0]) + bl),
           _pt(candles, n - 1, al * (n - 1) + bl)]
    both_touch = len(xsu) >= 2 and len(xsl) >= 2
    if not both_touch:
        return []

    def mk(ptype, name, direction, expl, conf):
        return [{
            "type": ptype, "name": name, "direction": direction,
            "status": "forming", "confidence": round(conf, 2),
            "points": pts, "explanation": expl,
        }]

    # parallel -> channel
    if abs(au - al) < flat:
        if au > flat:
            return mk("channel", "Восходящий канал", "bullish",
                      "Цена движется в восходящем канале: покупки от нижней "
                      "границы, цели у верхней. Пробой нижней границы — сигнал слабости.", 0.6)
        if au < -flat:
            return mk("channel", "Нисходящий канал", "bearish",
                      "Нисходящий канал: продажи от верхней границы. Пробой верхней "
                      "границы вверх может означать разворот.", 0.6)
        return mk("channel", "Боковой канал", "neutral",
                  "Флэтовый диапазон: торговля от границ, пробой задаёт направление.", 0.55)
    # converging shapes
    if conv:
        if abs(au) < flat and al > flat:
            return mk("triangle", "Восходящий треугольник", "bullish",
                      "Плоское сопротивление и растущие минимумы — покупатели давят. "
                      "Статистически чаще пробивается вверх.", 0.65)
        if abs(al) < flat and au < -flat:
            return mk("triangle", "Нисходящий треугольник", "bearish",
                      "Плоская поддержка и снижающиеся максимумы — продавцы давят. "
                      "Чаще пробивается вниз.", 0.65)
        if au < -flat and al > flat:
            return mk("triangle", "Симметричный треугольник", "neutral",
                      "Сжатие волатильности: рынок копит энергию, направление задаст "
                      "пробой одной из сторон.", 0.6)
        if au > flat and al > flat:
            return mk("wedge", "Восходящий клин", "bearish",
                      "Восходящий клин: рост выдыхается (сходящиеся линии). "
                      "Классически разрешается вниз.", 0.6)
        if au < -flat and al < -flat:
            return mk("wedge", "Нисходящий клин", "bullish",
                      "Нисходящий клин: падение замедляется. Классически "
                      "разрешается вверх.", 0.6)
    return []


def _double_extremes(candles, high, low, close, ph, pl, atr) -> list[dict]:
    out: list[dict] = []
    price = float(close[-1])
    # double top: two similar pivot highs, valley between, neckline break
    if len(ph) >= 2:
        i1, i2 = ph[-2], ph[-1]
        if i2 - i1 >= 8 and abs(high[i1] - high[i2]) <= 0.35 * atr:
            valley = float(low[i1:i2 + 1].min())
            top = max(float(high[i1]), float(high[i2]))
            if top - valley >= 1.2 * atr:
                confirmed = price < valley
                out.append({
                    "type": "double_top", "name": "Двойная вершина",
                    "direction": "bearish",
                    "status": "confirmed" if confirmed else "forming",
                    "confidence": 0.75 if confirmed else 0.55,
                    "points": [_pt(candles, i1, high[i1]), _pt(candles, i2, high[i2])],
                    "level": round(valley, 6),
                    "explanation": "Две вершины на одном уровне: покупатели дважды не "
                                   f"смогли пройти выше. Подтверждение — закрытие ниже "
                                   f"линии шеи {valley:.5g}"
                                   + (" (уже произошло — цели ниже)." if confirmed
                                      else " (ещё не произошло)."),
                })
    if len(pl) >= 2:
        i1, i2 = pl[-2], pl[-1]
        if i2 - i1 >= 8 and abs(low[i1] - low[i2]) <= 0.35 * atr:
            ridge = float(high[i1:i2 + 1].max())
            bottom = min(float(low[i1]), float(low[i2]))
            if ridge - bottom >= 1.2 * atr:
                confirmed = price > ridge
                out.append({
                    "type": "double_bottom", "name": "Двойное дно",
                    "direction": "bullish",
                    "status": "confirmed" if confirmed else "forming",
                    "confidence": 0.75 if confirmed else 0.55,
                    "points": [_pt(candles, i1, low[i1]), _pt(candles, i2, low[i2])],
                    "level": round(ridge, 6),
                    "explanation": "Два минимума на одном уровне: продавцы дважды не "
                                   f"продавили ниже. Подтверждение — закрытие выше "
                                   f"линии шеи {ridge:.5g}"
                                   + (" (уже произошло — цели выше)." if confirmed
                                      else " (ещё не произошло)."),
                })
    return out


def _head_shoulders(candles, high, low, close, ph, pl, atr) -> list[dict]:
    out: list[dict] = []
    price = float(close[-1])
    if len(ph) >= 3:
        l_, h_, r_ = ph[-3], ph[-2], ph[-1]
        if (high[h_] - max(high[l_], high[r_]) >= 0.6 * atr
                and abs(high[l_] - high[r_]) <= 0.9 * atr):
            neck = float(min(low[l_:h_ + 1].min(), low[h_:r_ + 1].min()))
            confirmed = price < neck
            out.append({
                "type": "head_shoulders", "name": "Голова и плечи",
                "direction": "bearish",
                "status": "confirmed" if confirmed else "forming",
                "confidence": 0.8 if confirmed else 0.55,
                "points": [_pt(candles, l_, high[l_]), _pt(candles, h_, high[h_]),
                           _pt(candles, r_, high[r_])],
                "level": round(neck, 6),
                "explanation": "Разворотная формация: правое плечо ниже головы — "
                               f"импульс роста угасает. Пробой шеи {neck:.5g} "
                               + ("подтверждён — цель ≈ высота головы вниз."
                                  if confirmed else "ещё не подтверждён."),
            })
    if len(pl) >= 3:
        l_, h_, r_ = pl[-3], pl[-2], pl[-1]
        if (min(low[l_], low[r_]) - low[h_] >= 0.6 * atr
                and abs(low[l_] - low[r_]) <= 0.9 * atr):
            neck = float(max(high[l_:h_ + 1].max(), high[h_:r_ + 1].max()))
            confirmed = price > neck
            out.append({
                "type": "inv_head_shoulders", "name": "Перевёрнутые голова и плечи",
                "direction": "bullish",
                "status": "confirmed" if confirmed else "forming",
                "confidence": 0.8 if confirmed else 0.55,
                "points": [_pt(candles, l_, low[l_]), _pt(candles, h_, low[h_]),
                           _pt(candles, r_, low[r_])],
                "level": round(neck, 6),
                "explanation": "Разворотная формация вверх: правое плечо выше головы. "
                               f"Пробой шеи {neck:.5g} "
                               + ("подтверждён — цель ≈ высота головы вверх."
                                  if confirmed else "ещё не подтверждён."),
            })
    return out


def _flags(candles, high, low, close, atr) -> list[dict]:
    """Impulse >=3 ATR within <=15 bars, then a tight consolidation."""
    n = len(close)
    look = min(40, n - 5)
    seg_start = n - look
    best = None
    for i in range(seg_start, n - 6):
        for j in range(i + 3, min(i + 16, n - 4)):
            move = float(close[j] - close[i])
            if abs(move) >= 3 * atr:
                best = (i, j, move)
    if not best:
        return []
    i, j, move = best
    tail_high = float(high[j + 1:].max())
    tail_low = float(low[j + 1:].min())
    if (tail_high - tail_low) > 1.8 * atr or n - 1 - j > 20:
        return []
    direction = "bullish" if move > 0 else "bearish"
    # retracement against the impulse must stay shallow (< 50%)
    retrace = (float(close[-1]) - float(close[j])) / move
    if retrace < -0.5:
        return []
    conv = (float(high[j + 1:].std()) + float(low[j + 1:].std())) < 0.5 * atr
    name = "Вымпел" if conv else "Флаг"
    return [{
        "type": "pennant" if conv else "flag",
        "name": f"{name} ({'бычий' if move > 0 else 'медвежий'})",
        "direction": direction,
        "status": "forming",
        "confidence": 0.6,
        "points": [_pt(candles, i, close[i]), _pt(candles, j, close[j]),
                   _pt(candles, n - 1, close[-1])],
        "explanation": f"Импульс {move:+.5g} за {j - i} баров, затем узкая "
                       f"консолидация — паттерн продолжения. Пробой в сторону "
                       f"импульса ({'вверх' if move > 0 else 'вниз'}) наиболее вероятен.",
    }]


def _breakouts(candles, close, zones, atr) -> list[dict]:
    out: list[dict] = []
    n = len(close)
    price = float(close[-1])
    for z in zones[:5]:
        level = z["price"]
        recent = close[-6:]
        older = close[-16:-6]
        if len(older) < 5:
            continue
        was_below = float(np.median(older)) < level - 0.1 * atr
        was_above = float(np.median(older)) > level + 0.1 * atr
        crossed_up = was_below and any(c > level + 0.25 * atr for c in recent)
        crossed_dn = was_above and any(c < level - 0.25 * atr for c in recent)
        if crossed_up and price > level + 0.25 * atr:
            out.append(_bo(candles, n, level, "breakout", "bullish",
                           f"Пробой сопротивления {level:.5g} с закрытием выше. "
                           f"Уровень теперь может работать поддержкой."))
        elif crossed_up and price <= level:
            out.append(_bo(candles, n, level, "false_breakout", "bearish",
                           f"Ложный пробой сопротивления {level:.5g}: цена вернулась "
                           f"под уровень — ловушка для покупателей, риск движения вниз."))
        elif crossed_dn and price < level - 0.25 * atr:
            out.append(_bo(candles, n, level, "breakout", "bearish",
                           f"Пробой поддержки {level:.5g} с закрытием ниже. "
                           f"Уровень теперь может работать сопротивлением."))
        elif crossed_dn and price >= level:
            out.append(_bo(candles, n, level, "false_breakout", "bullish",
                           f"Ложный пробой поддержки {level:.5g}: цена вернулась выше — "
                           f"ловушка для продавцов, возможен ход вверх."))
    return out


def _bo(candles, n, level, ptype, direction, expl) -> dict:
    return {
        "type": ptype,
        "name": "Пробой уровня" if ptype == "breakout" else "Ложный пробой",
        "direction": direction, "status": "confirmed",
        "confidence": 0.7 if ptype == "breakout" else 0.65,
        "points": [_pt(candles, max(0, n - 10), level), _pt(candles, n - 1, level)],
        "level": round(level, 6),
        "explanation": expl,
    }


def _fibonacci(candles, high, low) -> dict[str, Any] | None:
    n = len(high)
    win = min(100, n)
    h_idx = int(np.argmax(high[-win:])) + n - win
    l_idx = int(np.argmin(low[-win:])) + n - win
    hi, lo = float(high[h_idx]), float(low[l_idx])
    if hi - lo <= 0:
        return None
    up = l_idx < h_idx  # last major swing is upward
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = {f"{r:.3f}": round(hi - (hi - lo) * r if up else lo + (hi - lo) * r, 6)
              for r in ratios}
    return {
        "direction": "up" if up else "down",
        "swing_high": {"time": candles[h_idx]["time"], "price": hi},
        "swing_low": {"time": candles[l_idx]["time"], "price": lo},
        "levels": levels,
    }
