"""Несут ли факторы формулы информацию — и разную ли?

Два вопроса, на которые проект до сих пор не отвечал:

1. Information Coefficient каждого фактора: ранговая корреляция значения
   фактора с будущей доходностью. IC = 0 означает «предсказательной силы нет».
   Ориентир из литературы: у документированных премий (моментум, value,
   quality, low-vol) IC держится в диапазоне 0.04-0.10 и почти никогда не
   превышает 0.10. Всё, что заметно ниже 0.02 — шум.

2. Корреляция факторов между собой. В формуле восемь технических факторов, и
   все они посчитаны по одному и тому же ряду цен: trend, tsmom, kama_er,
   macd, roc — это пять способов измерить одно движение. Если корреляции
   высокие, «совокупная оценка одиннадцати факторов» на деле складывает один
   фактор восемь раз, и её порог ничего не фильтрует.

Запуск:
    docker compose exec -T backend python3 -m app.tools.factors
    docker compose exec -T backend python3 -m app.tools.factors --tf 1h --horizon 6
"""

import argparse
import asyncio
from typing import Any

import numpy as np

from ..backtest.engine import WARMUP, _precompute, _snap
from ..database import SessionLocal
from ..services.runtime import get_app_config
from ..signals import exogenous as exo
from ..signals.engine import BASE_WEIGHTS, score_components
from .sweep import DEFAULT_INSTRUMENTS, _load

# факторы, которые движок считает из цены; ИИ-термины и htf здесь недоступны
PRICE_FACTORS = ("trend", "tsmom", "kama_er", "macd", "rsi", "stoch",
                 "bollinger", "roc")
# кандидаты из signals.exogenous — информация ИЗВНЕ ценового ряда инструмента
NEW_FACTORS = ("session", "vol_regime", "dollar_align")
ALL_FACTORS = PRICE_FACTORS + NEW_FACTORS


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Ранговая корреляция без scipy."""
    if len(a) < 30:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    ra -= ra.mean()
    rb -= rb.mean()
    d = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return float((ra * rb).sum() / d) if d > 0 else 0.0


def _collect(candles: list[dict], horizon: int, min_adx: float,
             instrument: str = "", basket: dict[str, np.ndarray] | None = None
             ) -> tuple[dict[str, list[float]], list[float], list[float]]:
    """Значения факторов, совокупная оценка и будущая доходность по барам.

    Доходность нормируется на ATR: иначе бары с разной волатильностью нельзя
    складывать в один ряд, и корреляция поедет за волатильностью, а не за
    предсказанием.
    """
    pre = _precompute(candles)
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    atr = pre["atr14"]
    cols: dict[str, list[float]] = {f: [] for f in ALL_FACTORS}
    scores: list[float] = []
    fwd: list[float] = []

    for i in range(WARMUP, len(candles) - horizon):
        snap = _snap(pre, i)
        if snap["atr14"] is None or snap["ema20"] is None or not snap["atr14"]:
            continue
        comp, _, score, _ = score_components(snap, 0.0, 0.0, min_adx, ai_weight=0.0)
        for f in PRICE_FACTORS:
            cols[f].append(float(comp.get(f, 0.0)))

        ts = candles[i]["time"]
        cols["session"].append(exo.session_bias(instrument, ts))
        cols["vol_regime"].append(exo.vol_regime(atr, i))
        # движение доллара по остальным парам на этом же баре
        moves: dict[str, float] = {}
        if basket:
            for sym, series in basket.items():
                v = series[i] if i < len(series) else np.nan
                if not np.isnan(v):
                    moves[sym] = float(v)
        cols["dollar_align"].append(exo.dollar_align(moves, instrument))

        scores.append(float(score))
        fwd.append(float((close[i + horizon] - close[i]) / snap["atr14"]))
    return cols, scores, fwd


def _basket(data: dict[str, list]) -> dict[str, np.ndarray]:
    """Доходность последнего бара, нормированная на ATR, по каждой паре —
    выровненная по индексу бара. Нужна фактору dollar_align."""
    out: dict[str, np.ndarray] = {}
    for sym, candles in data.items():
        if "USD" not in sym.split("_"):
            continue
        pre = _precompute(candles)
        close = np.array([c["close"] for c in candles], dtype=np.float64)
        atr = pre["atr14"]
        r = np.full(len(close), np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            r[1:] = (close[1:] - close[:-1]) / atr[1:]
        out[sym] = np.clip(r, -3.0, 3.0)
    return out


def _report(cols: dict[str, list[float]], scores: list[float],
            fwd: list[float], horizon: int) -> None:
    y = np.array(fwd)
    n = len(y)
    print(f"наблюдений: {n}, горизонт: {horizon} баров\n")

    def verdict(ic: float) -> str:
        return ("шум" if abs(ic) < 0.02 else
                "слабо" if abs(ic) < 0.04 else
                "в норме литературы" if abs(ic) < 0.10 else "подозрительно много")

    print("INFORMATION COEFFICIENT (ранговая корреляция с будущей доходностью)")
    print("ориентир: у документированных премий IC = 0.04-0.10\n")

    rows = [(f, _spearman(np.array(cols[f]), y)) for f in PRICE_FACTORS]
    print(f"{'ФАКТОРЫ ФОРМУЛЫ (из цены)':26} {'вес':>6} {'IC':>8}  оценка")
    for f, ic in sorted(rows, key=lambda r: -abs(r[1])):
        print(f"  {f:24} {BASE_WEIGHTS.get(f, 0.0):6.2f} {ic:+8.4f}  {verdict(ic)}")

    new_rows = [(f, _spearman(np.array(cols[f]), y)) for f in NEW_FACTORS
                if any(v != 0.0 for v in cols[f])]
    if new_rows:
        print(f"\n{'КАНДИДАТЫ (вне цены инструмента)':26} {'':6} {'IC':>8}  оценка")
        for f, ic in sorted(new_rows, key=lambda r: -abs(r[1])):
            nz = sum(1 for v in cols[f] if v != 0.0)
            print(f"  {f:24} {'':6} {ic:+8.4f}  {verdict(ic)} "
                  f"(ненулевых {100*nz/max(1,len(y)):.0f}%)")
        best_old = max((abs(ic) for _, ic in rows), default=0.0)
        best_new = max((abs(ic) for _, ic in new_rows), default=0.0)
        if best_new > best_old:
            print(f"\n  -> лучший новый ({best_new:.4f}) СИЛЬНЕЕ лучшего "
                  f"старого ({best_old:.4f}) — стоит включать в формулу")
        else:
            print(f"\n  -> лучший новый ({best_new:.4f}) не превосходит "
                  f"лучший старый ({best_old:.4f})")

    ic_score = _spearman(np.array(scores), y)
    print(f"\n{'СОВОКУПНАЯ ОЦЕНКА':14} {'':6} {ic_score:+8.4f} {abs(ic_score):7.4f}")
    best = max(abs(ic) for _, ic in rows) if rows else 0.0
    if abs(ic_score) <= best + 1e-9:
        print("  -> смесь НЕ ЛУЧШЕ лучшего одиночного фактора: складывать их "
              "вместе смысла не даёт")
    else:
        print(f"  -> смесь лучше лучшего одиночного ({best:.4f}) — "
              f"комбинирование что-то добавляет")

    print("\nКОРРЕЛЯЦИЯ ФАКТОРОВ МЕЖДУ СОБОЙ")
    shown = [f for f in ALL_FACTORS if any(v != 0.0 for v in cols[f])]
    mat = {f: np.array(cols[f]) for f in shown}
    hdr = "".join(f"{f[:6]:>8}" for f in shown)
    print(f"{'':14}{hdr}")
    high: list[tuple[str, str, float]] = []
    for a in shown:
        line = f"{a:14}"
        for b in shown:
            c = _spearman(mat[a], mat[b])
            line += f"{c:8.2f}"
            if a < b and abs(c) >= 0.6:
                high.append((a, b, c))
        print(line)

    if high:
        print("\nПАРЫ, КОТОРЫЕ ИЗМЕРЯЮТ ПОЧТИ ОДНО И ТО ЖЕ (|corr| >= 0.6):")
        for a, b, c in sorted(high, key=lambda x: -abs(x[2])):
            print(f"  {a:12} ~ {b:12} {c:+.2f}")
        w = sum(BASE_WEIGHTS.get(f, 0) for f in
                {x for pair in high for x in pair[:2]})
        print(f"  суммарный вес задействованных факторов: {w:.2f} из 1.00")
    else:
        print("\nсильно скоррелированных пар нет — факторы независимы")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--horizon", type=int, default=6,
                    help="через сколько баров считать доходность")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        from ..services.settings import get_settings

        st = get_settings(db)
        cfg = get_app_config(db)
        blocked = set(st.get("blocked_instruments") or [])
        instruments = [s for s in dict.fromkeys(
            DEFAULT_INSTRUMENTS + list(cfg.get("watchlist") or []))
            if s not in blocked]
        print(f"Загрузка свечей {args.tf}:")
        data = await _load(db, instruments, args.tf, args.bars)
        min_adx = st["min_adx"]
    finally:
        db.close()

    if not data:
        print("\nНет реальных данных.")
        return

    basket = _basket(data)
    all_cols: dict[str, list[float]] = {f: [] for f in ALL_FACTORS}
    all_scores: list[float] = []
    all_fwd: list[float] = []
    for sym, candles in data.items():
        cols, scores, fwd = _collect(candles, args.horizon, min_adx,
                                     sym, basket)
        for f in ALL_FACTORS:
            all_cols[f].extend(cols[f])
        all_scores.extend(scores)
        all_fwd.extend(fwd)

    print(f"\n{'='*72}\nАНАЛИЗ ФАКТОРОВ · {args.tf}\n{'='*72}")
    _report(all_cols, all_scores, all_fwd, args.horizon)


if __name__ == "__main__":
    asyncio.run(main())
