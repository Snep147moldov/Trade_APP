"""Проверка настройки на данных, которых оптимизация НЕ видела.

Перебор нашёл 58 прибыльных сочетаний из 720 при торговле ПРОТИВ оценки
движка. Но перебор всегда что-нибудь находит: из 720 вариантов часть окажется
хорошей случайно. Единственный честный ответ даёт разбиение по времени —
подобрать на первой половине истории и проверить на второй, которую подбор не
трогал.

Заодно считает результат по ЧАСУ ВХОДА: часть суток может быть прибыльной, а
часть — съедать её. Ликвидность и спред в 03:00 и в 14:00 несопоставимы.

Запуск:
    docker compose exec -T backend python3 -m app.tools.validate --invert
    docker compose exec -T backend python3 -m app.tools.validate --invert \\
        --min-score 0.25 --rr 1.8 --sl 2.0
"""

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from ..backtest.engine import DEFAULT_PARAMS, simulate
from ..database import SessionLocal
from ..services.runtime import get_app_config
from .sweep import DEFAULT_INSTRUMENTS, _load


def _stats(trades: list[dict]) -> dict[str, Any]:
    rs = [float(t["r"]) for t in trades if t.get("r") is not None]
    if not rs:
        return {"trades": 0}
    wins = [r for r in rs if r > 0]
    gross_w = sum(wins)
    gross_l = -sum(r for r in rs if r <= 0)
    return {
        "trades": len(rs),
        "win_rate": 100.0 * len(wins) / len(rs),
        "expectancy_r": sum(rs) / len(rs),
        "total_r": sum(rs),
        "profit_factor": (gross_w / gross_l) if gross_l > 0 else None,
    }


def _line(label: str, s: dict[str, Any]) -> str:
    if not s.get("trades"):
        return f"{label:26} нет сделок"
    pf = s["profit_factor"]
    return (f"{label:26} {s['trades']:5} {s['win_rate']:6.1f}% "
            f"{s['expectancy_r']:+8.3f} {s['total_r']:+9.1f} "
            f"{(f'{pf:.2f}' if pf else '  -  '):>6}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--min-score", type=float, default=0.25)
    ap.add_argument("--rr", type=float, default=1.8)
    ap.add_argument("--sl", type=float, default=2.0)
    ap.add_argument("--expiry", type=int, default=96)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--measured", action="store_true",
                    help="знаки факторов по замеренному IC")
    ap.add_argument("--spread", type=float, default=1.0)
    ap.add_argument("--weekend-flat", action="store_true",
                    help="закрывать позиции перед выходными")
    ap.add_argument("--factors", default="",
                    help="оставить только эти факторы, через запятую")
    ap.add_argument("--trend-hours", default="",
                    help="часы UTC через запятую, где формула НЕ инвертируется")
    ap.add_argument("--be", type=float, default=0.0,
                    help="перенос стопа в безубыток при +N R (0 = выкл)")
    ap.add_argument("--be-lock", type=float, default=0.0,
                    help="сколько прибыли запирает перенос, в R")
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
    finally:
        db.close()
    if not data:
        print("\nНет реальных данных.")
        return

    params = {**DEFAULT_PARAMS, "min_score": args.min_score,
              "risk_reward": args.rr, "sl_atr_multiple": args.sl,
              "expiry_bars": args.expiry, "invert_signal": args.invert,
              "factor_signs": "measured" if args.measured else "original",
              "spread_pips": args.spread, "bars": args.bars,
              "weekend_flat": args.weekend_flat,
              "trend_hours_utc": tuple(
                  int(x) for x in args.trend_hours.split(",") if x.strip()),
              "breakeven_at_r": args.be, "breakeven_lock_r": args.be_lock,
              "factor_subset": tuple(
                  x.strip() for x in args.factors.split(",") if x.strip())}

    print(f"\n{'='*74}")
    print(f"НАСТРОЙКА: порог {args.min_score}, R:R {args.rr}, SL {args.sl}xATR, "
          f"выход {args.expiry if args.expiry < 96 else 'нет'}, "
          + ("ПРОТИВ оценки" if args.invert else
             "знаки по замеру" if args.measured else "по оценке")
          + (f", трендовые часы {args.trend_hours}" if args.trend_hours else "")
          + (f", факторы: {args.factors}" if args.factors else ""))
    print(f"{'='*74}")

    # ---- разбиение по времени: половина на подбор, половина на проверку
    def split(p: dict[str, Any]) -> tuple[list[dict], list[dict]]:
        a: list[dict] = []
        b: list[dict] = []
        for sym, candles in data.items():
            mid = candles[len(candles) // 2]["time"]
            for t in simulate(candles, sym, p)["trades"]:
                (a if t["entry_time"] < mid else b).append(t)
        return a, b

    first, second = split(params)

    hdr = (f"{'':26} {'сделок':>5} {'winrate':>7} {'E[R]':>8} "
           f"{'сумма R':>9} {'PF':>6}")
    print("\nПРОВЕРКА НА НЕВИДЕННЫХ ДАННЫХ")
    print(hdr)
    print(_line("первая половина", _stats(first)))
    print(_line("вторая половина", _stats(second)))
    print(_line("всё вместе", _stats(first + second)))

    a, b = _stats(first), _stats(second)
    if a.get("trades") and b.get("trades"):
        ea, eb = a["expectancy_r"], b["expectancy_r"]
        if ea > 0 and eb > 0:
            print("\n  -> обе половины в плюсе: результат не выглядит "
                  "подгонкой под одну эпоху")
        elif ea > 0 > eb or eb > 0 > ea:
            print("\n  -> половины расходятся по знаку: скорее всего подгонка, "
                  "торговать на этом нельзя")
        else:
            print("\n  -> обе половины в минусе")

    # ---- по часу входа
    print("\nПО ЧАСУ ВХОДА (UTC; Бухарест = UTC+3 летом)")
    print(f"{'час':>4} {'Бух':>4} {'сделок':>7} {'winrate':>8} {'E[R]':>8} "
          f"{'сумма R':>9}")
    by_hour: dict[int, list[dict]] = {}
    for t in first + second:
        h = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).hour
        by_hour.setdefault(h, []).append(t)
    best_hours: list[tuple[int, float, int]] = []
    for h in sorted(by_hour):
        s = _stats(by_hour[h])
        if not s.get("trades"):
            continue
        best_hours.append((h, s["expectancy_r"], s["trades"]))
        mark = "  <<<" if s["expectancy_r"] > 0.05 else (
            "   xx" if s["expectancy_r"] < -0.05 else "")
        print(f"{h:4d} {(h+3) % 24:4d} {s['trades']:7} {s['win_rate']:7.1f}% "
              f"{s['expectancy_r']:+8.3f} {s['total_r']:+9.1f}{mark}")

    good = [h for h, e, n in best_hours if e > 0 and n >= 20]
    bad = [h for h, e, n in best_hours if e < -0.05 and n >= 20]
    if good:
        print(f"\n  прибыльные часы (UTC): {', '.join(map(str, good))}")
        print(f"  они же по Бухаресту:   "
              f"{', '.join(str((h+3) % 24) for h in good)}")
        only = [t for t in first + second
                if datetime.fromtimestamp(t["entry_time"],
                                          tz=timezone.utc).hour in good]
        print("\n" + hdr)
        print(_line("только эти часы", _stats(only)))
        print("  ВНИМАНИЕ: часы выбраны по этим же данным — это снова подгонка. "
              "Проверять отдельно.")
    if bad:
        print(f"\n  убыточные часы (UTC): {', '.join(map(str, bad))}")

    # ---- ЧЕСТНАЯ проверка отбора по часам: часы выбираются ТОЛЬКО по первой
    # половине, фильтр применяется ко второй, которую отбор не видел
    print(f"\n{'='*74}\nОТБОР ЧАСОВ БЕЗ ПОДГЛЯДЫВАНИЯ\n{'='*74}")
    fh: dict[int, list[dict]] = {}
    for t in first:
        h = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).hour
        fh.setdefault(h, []).append(t)
    drop = {h for h, ts in fh.items()
            if len(ts) >= 10 and _stats(ts)["expectancy_r"] < 0}
    print(f"часы, убыточные в ПЕРВОЙ половине (UTC): "
          f"{', '.join(map(str, sorted(drop))) or 'нет'}")
    kept = [t for t in second
            if datetime.fromtimestamp(t["entry_time"],
                                      tz=timezone.utc).hour not in drop]
    print("\nприменяем этот список ко ВТОРОЙ половине:")
    print(hdr)
    print(_line("вторая половина, всё", _stats(second)))
    print(_line("вторая, без тех часов", _stats(kept)))
    b_all, b_kept = _stats(second), _stats(kept)
    if b_all.get("trades") and b_kept.get("trades"):
        if b_kept["expectancy_r"] > b_all["expectancy_r"]:
            print("\n  -> отбор по часам ПОМОГАЕТ и на невиденных данных")
        else:
            print("\n  -> отбор по часам НЕ помогает: на первой половине он "
                  "нашёл случайность, а не закономерность")

    # ---- КОГДА ЗАБИРАТЬ ПРИБЫЛЬ
    # Наблюдение с живого счёта: сделки весь день стоят в плюсе, а к вечеру
    # отдают всё обратно. В пачке 07.09 четыре сигнала из одиннадцати закрылись
    # ровно в +0.00 EUR — они доходили до +1.3R, ловили перенесённый в
    # безубыток стоп и возвращались. Здесь проверяется, что дешевле: забирать
    # раньше (короткий тейк) или запирать часть прибыли переносом стопа.
    # Обе половины показаны отдельно: вариант, выигрывающий только на одной,
    # к торговле не годится.
    def compare(title: str, variants: list[tuple[str, dict]]) -> None:
        print(f"\n{'='*74}\n{title}\n{'='*74}")
        print(f"{'':26} {'сделок':>5} {'winrate':>7} {'E[R]':>8} "
              f"{'сумма R':>9} {'PF':>6}")
        for label, extra in variants:
            a, b = split({**params, **extra})
            print(_line(f"{label} · 1-я пол.", _stats(a)))
            print(_line(f"{label} · 2-я пол.", _stats(b)))

    compare("РАЗМЕР ТЕЙКА (стоп тот же, меняется только цель)",
            [(f"R:R {rr}", {"risk_reward": rr})
             for rr in (0.5, 0.8, 1.0, 1.3, args.rr)])

    compare("БЕЗУБЫТОК: сколько прибыли он запирает",
            [("без переноса", {"breakeven_at_r": 0.0}),
             ("+1.3R -> стоп в 0",
              {"breakeven_at_r": 1.3, "breakeven_lock_r": 0.0}),
             ("+1.3R -> запереть 0.5R",
              {"breakeven_at_r": 1.3, "breakeven_lock_r": 0.5}),
             ("+1.0R -> запереть 0.5R",
              {"breakeven_at_r": 1.0, "breakeven_lock_r": 0.5})])


if __name__ == "__main__":
    asyncio.run(main())
