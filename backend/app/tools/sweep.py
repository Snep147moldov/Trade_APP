"""Перебор параметров стратегии на РЕАЛЬНЫХ свечах.

Отвечает на вопрос, который до сих пор решался на глаз: какое сочетание порога
оценки, соотношения риск/прибыль и ширины стопа даёт лучшее матожидание — и
существует ли вообще положительное.

Считает по тому же движку, что торгует вживую (backtest.engine.simulate), и
отказывается работать на синтетических свечах: провайдер молча подставляет
симулятор, когда у него нет инструмента, а на сумме синусов трендовая стратегия
показывает winrate 65-85%, которого на рынке нет.

Запуск:
    docker compose exec -T backend python3 -m app.tools.sweep
    docker compose exec -T backend python3 -m app.tools.sweep --tf 1h --bars 2000
"""

import argparse
import asyncio
from typing import Any

from ..backtest.engine import simulate
from ..database import SessionLocal
from ..services.candles import get_candles, is_simulated
from ..services.runtime import get_app_config, get_credentials

# мажоры + кроссы, которые реально торгует брокер и по которым есть история
DEFAULT_INSTRUMENTS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD",
    "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY", "EUR_CAD", "AUD_NZD",
    "CAD_CHF", "GBP_CHF", "NZD_CAD",
]

MIN_SCORE_GRID = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
RISK_REWARD_GRID = [0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.5]
SL_ATR_GRID = [1.0, 1.5, 2.0]


async def _load(db, instruments: list[str], tf: str, bars: int) -> dict[str, list]:
    """Свечи по инструментам; синтетика отбрасывается с явным сообщением."""
    creds = get_credentials(db)
    out: dict[str, list] = {}
    for sym in instruments:
        try:
            candles = await get_candles(creds, sym, tf, bars)
        except Exception as exc:
            print(f"  {sym:9} пропущен: {type(exc).__name__}")
            continue
        candles = [c for c in candles if c["complete"]]
        if is_simulated(candles):
            print(f"  {sym:9} ПРОПУЩЕН: провайдер отдал синтетику")
            continue
        if len(candles) < 300:
            print(f"  {sym:9} пропущен: только {len(candles)} баров")
            continue
        out[sym] = candles
        print(f"  {sym:9} {len(candles)} баров")
    return out


def _pool(data: dict[str, list], params: dict[str, Any]) -> dict[str, Any]:
    """Один прогон сетки: сделки со всех инструментов складываются в общий
    пул, иначе матожидание считается по 3-4 сделкам на пару и это шум."""
    rs: list[float] = []
    wins = 0
    gross_w = gross_l = 0.0
    for sym, candles in data.items():
        r = simulate(candles, sym, params)
        for t in r["trades"]:
            rr = t.get("r")
            if rr is None:
                continue
            rs.append(float(rr))
            if t["pnl_eur"] > 0:
                wins += 1
                gross_w += t["pnl_eur"]
            else:
                gross_l -= t["pnl_eur"]
    n = len(rs)
    if not n:
        return {"trades": 0}
    exp_r = sum(rs) / n
    return {
        "trades": n,
        "win_rate": 100.0 * wins / n,
        "expectancy_r": exp_r,
        "total_r": sum(rs),
        "profit_factor": (gross_w / gross_l) if gross_l > 0 else None,
    }


def _fmt(row: dict[str, Any]) -> str:
    pf = row.get("profit_factor")
    return (f"{row['trades']:5} {row['win_rate']:6.1f}% "
            f"{row['expectancy_r']:+8.3f} {row['total_r']:+9.1f} "
            f"{(f'{pf:.2f}' if pf else '  -  '):>6}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--min-trades", type=int, default=40,
                    help="сочетания с меньшим числом сделок не показываются")
    ap.add_argument("--spread", type=float, default=1.0, help="спред, пунктов")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        cfg = get_app_config(db)
        watch = [s for s in (cfg.get("watchlist") or [])]
        instruments = list(dict.fromkeys(DEFAULT_INSTRUMENTS + watch))
        print(f"Загрузка свечей {args.tf}, до {args.bars} баров:")
        data = await _load(db, instruments, args.tf, args.bars)
    finally:
        db.close()

    if not data:
        print("\nНет реальных данных — перебор невозможен.")
        return
    print(f"\nИнструментов с реальными данными: {len(data)}\n")

    base = {"spread_pips": args.spread, "slippage_pips": 0.2,
            "risk_per_trade_pct": 1.0, "initial_equity": 10000.0,
            "bars": args.bars}

    results = []
    for sl in SL_ATR_GRID:
        for ms in MIN_SCORE_GRID:
            for rr in RISK_REWARD_GRID:
                row = _pool(data, {**base, "min_score": ms,
                                   "risk_reward": rr, "sl_atr_multiple": sl})
                if row["trades"] < args.min_trades:
                    continue
                row.update(min_score=ms, risk_reward=rr, sl_atr=sl)
                results.append(row)

    if not results:
        print(f"Ни одно сочетание не дало {args.min_trades}+ сделок.")
        return

    hdr = (f"{'порог':>6} {'R:R':>5} {'SL':>4} | {'сделок':>5} {'winrate':>7} "
           f"{'E[R]':>8} {'сумма R':>9} {'PF':>6}")
    results.sort(key=lambda r: -r["expectancy_r"])
    print("ЛУЧШИЕ 15 ПО МАТОЖИДАНИЮ")
    print(hdr)
    for r in results[:15]:
        print(f"{r['min_score']:6.2f} {r['risk_reward']:5.1f} {r['sl_atr']:4.1f} | "
              + _fmt(r))

    print("\nХУДШИЕ 5")
    for r in results[-5:]:
        print(f"{r['min_score']:6.2f} {r['risk_reward']:5.1f} {r['sl_atr']:4.1f} | "
              + _fmt(r))

    cur = [r for r in results
           if abs(r["min_score"] - 0.45) < 1e-9 and abs(r["risk_reward"] - 1.8) < 1e-9
           and abs(r["sl_atr"] - 1.5) < 1e-9]
    if cur:
        print("\nТЕКУЩАЯ НАСТРОЙКА (0.45 / 1.8 / 1.5)")
        print(hdr)
        print(f"{0.45:6.2f} {1.8:5.1f} {1.5:4.1f} | " + _fmt(cur[0]))

    pos = [r for r in results if r["expectancy_r"] > 0]
    print(f"\nСочетаний с положительным матожиданием: {len(pos)} из {len(results)}")
    if not pos:
        print("НИ ОДНО сочетание параметров не выходит в плюс на этих данных.")


if __name__ == "__main__":
    asyncio.run(main())
