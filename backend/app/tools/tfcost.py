"""Во что обходится вход на каждом таймфрейме — до всякой формулы.

Стоп считается как sl_atr_multiple * ATR14, то есть сжимается вместе с
таймфреймом: ATR(1m) в десятки раз меньше ATR(1h). Спред при этом не меняется
вообще. Поэтому на коротких таймфреймах круговой спред может съесть весь риск,
и тогда сделка не может выйти в плюс ни при каком качестве сигнала — ровно та
арифметика, которую мы уже видели на кроссах при закрытом рынке.

Здесь это меряется, а не предполагается: реальные свечи, реальные bid/ask у
брокера, и доля риска, которая уходит в издержки на входе и выходе.

Запуск:
    docker compose exec -T backend python3 -m app.tools.tfcost
    docker compose exec -T backend python3 -m app.tools.tfcost --tf 1m,5m,15m,40m,1h
"""

import argparse
import asyncio
from statistics import median
from typing import Any

from ..indicators import core as ind
from ..database import SessionLocal
from ..services import mt5 as mt5_svc
from ..services.candles import get_candles, is_simulated, pip_size
from ..services.runtime import get_app_config, get_credentials
from ..services.settings import get_settings
from .sweep import DEFAULT_INSTRUMENTS

import numpy as np


async def _stop_pips(creds: dict, sym: str, tf: str, mult: float) -> float | None:
    """Ширина стопа в пунктах на этом таймфрейме, по последним свечам."""
    try:
        candles = await get_candles(creds, sym, tf, 120)
    except Exception:
        return None
    candles = [c for c in candles if c["complete"]]
    if len(candles) < 30 or is_simulated(candles):
        return None
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    atr = ind.atr(high, low, close, 14)
    last = float(atr[-1])
    if not last or last != last:
        return None
    pip = pip_size(sym)
    return (mult * last / pip) if pip else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1m,5m,15m,40m,1h,4h")
    ap.add_argument("--pairs", type=int, default=8,
                    help="сколько пар опросить (каждая стоит запросов)")
    args = ap.parse_args()
    timeframes = [t.strip() for t in args.tf.split(",") if t.strip()]

    db = SessionLocal()
    try:
        st, cfg, creds = get_settings(db), get_app_config(db), get_credentials(db)
        mult = float(st["sl_atr_multiple"])
        limit = float(st.get("max_cost_ratio", 0.25))
        blocked = set(st.get("blocked_instruments") or [])
        pairs = [s for s in dict.fromkeys(
            list(cfg.get("watchlist") or []) + DEFAULT_INSTRUMENTS)
            if s not in blocked][:args.pairs]

        print(f"стоп = {mult} x ATR14 · порог издержек {limit*100:.0f}% от риска")
        print(f"пары: {', '.join(pairs)}\n")

        # спред у брокера от таймфрейма не зависит — спрашиваем один раз
        spread: dict[str, float] = {}
        for sym in pairs:
            q = await mt5_svc.symbol_price(db, sym)
            if q.get("ok"):
                spread[sym] = q["spread"] / pip_size(sym)
        if not spread:
            print("брокер не отдал котировки — без них сравнивать не с чем")
            return

        print(f"{'тф':>4} {'стоп, п. (медиана)':>20} {'спред, п.':>11} "
              f"{'туда-обратно от R':>19} {'пар проходит':>14}")
        rows: list[tuple[str, float, int, int]] = []
        for tf in timeframes:
            costs: list[float] = []
            stops: list[float] = []
            passed = 0
            for sym in pairs:
                if sym not in spread:
                    continue
                sp_pips = await _stop_pips(creds, sym, tf, mult)
                if not sp_pips or sp_pips <= 0:
                    continue
                cost = 2.0 * spread[sym] / sp_pips
                stops.append(sp_pips)
                costs.append(cost)
                if cost <= limit:
                    passed += 1
            if not costs:
                print(f"{tf:>4} {'нет данных':>20}")
                continue
            med_cost = median(costs)
            print(f"{tf:>4} {median(stops):20.1f} {median(spread.values()):11.2f} "
                  f"{med_cost*100:18.0f}% {passed:8} из {len(costs)}")
            rows.append((tf, med_cost, passed, len(costs)))

        print()
        for tf, cost, passed, total in rows:
            if cost >= 1.0:
                print(f"  {tf}: спред больше всей дистанции до стопа "
                      f"({cost*100:.0f}%) — сделка не может выйти в плюс")
            elif not passed:
                print(f"  {tf}: ни одна пара не проходит порог издержек — "
                      f"гейт отклонит все сигналы")
            elif passed < total:
                print(f"  {tf}: торгуемы {passed} пар из {total}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
