"""Куда цена успевает сходить ПОСЛЕ входа, до того как сделка закроется.

Отвечает на наблюдение пользователя: «сигнал прав на первой свече, а дальше
уходит в минус». Если так, то преимущество формулы существует, но короткое, и
тейк-профит на 1.8R просто не успевает исполниться.

Для каждой сделки считаются:
  MFE  максимальный ход В ПОЛЬЗУ сделки, в R   (сколько можно было забрать)
  MAE  максимальный ход ПРОТИВ, в R            (сколько пришлось пересидеть)
и то, на какой по счёту свече достигнут максимум прибыли.

Главный вывод даёт таблица «сколько сделок дошли бы до тейка на уровне X R» —
она прямо показывает, какой тейк-профит забрал бы больше всего денег.

Запуск:
    docker compose exec -T backend python3 -m app.tools.excursion
    docker compose exec -T backend python3 -m app.tools.excursion --tf 1h --bars 1500
"""

import argparse
import asyncio
from typing import Any

from ..backtest.engine import DEFAULT_PARAMS, simulate
from ..database import SessionLocal
from ..services.candles import get_candles, is_simulated
from ..services.runtime import get_app_config, get_credentials
from .sweep import DEFAULT_INSTRUMENTS, _load

# уровни тейк-профита, которые проверяем «а если бы выходили здесь»
TP_LEVELS = [0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 1.8, 2.2, 2.5, 3.0]


def _excursions(candles: list[dict], instrument: str,
                params: dict[str, Any]) -> list[dict[str, Any]]:
    """Прогоняем движок, затем по каждой сделке смотрим ход цены внутри её
    жизни: от входа до фактического выхода."""
    res = simulate(candles, instrument, params)
    by_time = {c["time"]: i for i, c in enumerate(candles)}
    out = []
    for t in res["trades"]:
        i0 = by_time.get(t["entry_time"])
        i1 = by_time.get(t["exit_time"])
        if i0 is None or i1 is None or i1 <= i0:
            continue
        entry = t["entry"]
        # дистанцию риска берём из движка, а не из округлённых entry/sl
        risk = t.get("risk_dist") or abs(entry - t["sl"])
        if risk <= 0:
            continue
        buy = t["direction"] == "BUY"
        mfe = mae = 0.0
        bar_of_peak = 0
        for k in range(i0 + 1, min(i1 + 1, len(candles))):
            c = candles[k]
            fav = (c["high"] - entry) if buy else (entry - c["low"])
            adv = (entry - c["low"]) if buy else (c["high"] - entry)
            if fav / risk > mfe:
                mfe = fav / risk
                bar_of_peak = k - i0
            mae = max(mae, adv / risk)
        out.append({"mfe": mfe, "mae": mae, "bars_to_peak": bar_of_peak,
                    "bars_held": i1 - i0, "r": float(t["r"]),
                    "win": t["pnl_eur"] > 0, "instrument": instrument})
    return out


def _report(rows: list[dict[str, Any]], rr: float) -> None:
    n = len(rows)
    if not n:
        print("нет сделок")
        return
    wins = [r for r in rows if r["win"]]
    losers = [r for r in rows if not r["win"]]

    print(f"сделок {n} · выигрышных {len(wins)} ({100*len(wins)/n:.1f}%)\n")
    print(f"{'':22} {'все':>8} {'выигрыши':>10} {'убытки':>9}")
    for lbl, key in [("MFE (ход в плюс), R", "mfe"),
                     ("MAE (ход в минус), R", "mae"),
                     ("баров до пика", "bars_to_peak"),
                     ("баров в сделке", "bars_held")]:
        a = sum(r[key] for r in rows) / n
        w = sum(r[key] for r in wins) / len(wins) if wins else 0
        l = sum(r[key] for r in losers) / len(losers) if losers else 0
        print(f"{lbl:22} {a:8.2f} {w:10.2f} {l:9.2f}")

    # стоп обязан ограничивать MAE единицей R; заметно больше — признак того,
    # что по инструменту считается мусор (мелкая цена, кривой контракт)
    per: dict[str, list] = {}
    for r in rows:
        per.setdefault(r["instrument"], []).append(r["mae"])
    bad = [(s, sum(v) / len(v), len(v)) for s, v in per.items()
           if sum(v) / len(v) > 1.6]
    if bad:
        print("\n⚠️ ИНСТРУМЕНТЫ С НЕПРАВДОПОДОБНЫМ MAE (стоп должен держать ~1R):")
        for s, m, k in sorted(bad, key=lambda x: -x[1]):
            print(f"   {s:9} средний MAE {m:6.2f}R по {k} сделкам")
        print("   их стоит исключить из выводов — цифры по ним недостоверны")

    print(f"\nУБЫТОЧНЫЕ СДЕЛКИ: успевали ли они побывать в плюсе?")
    for lvl in [0.25, 0.5, 0.75, 1.0, 1.5]:
        k = sum(1 for r in losers if r["mfe"] >= lvl)
        share = 100 * k / len(losers) if losers else 0
        print(f"  доходили до +{lvl:.2f}R: {k:4} из {len(losers)} ({share:5.1f}%)")

    print(f"\nЕСЛИ БЫ ТЕЙК СТОЯЛ ЗДЕСЬ (стоп -1R, тот же вход)")
    print(f"{'тейк':>6} {'winrate':>8} {'E[R]':>9} {'сумма R':>10}")
    best = None
    for tp in TP_LEVELS:
        hit = [r for r in rows if r["mfe"] >= tp]
        # не дошедшие до тейка считаем по стопу: -1R, кроме тех, кто и стоп не
        # тронул — им ставим фактический результат сделки
        tot = 0.0
        for r in rows:
            if r["mfe"] >= tp:
                tot += tp
            elif r["mae"] >= 1.0:
                tot -= 1.0
            else:
                tot += r["r"]
        exp = tot / n
        wr = 100 * len(hit) / n
        mark = ""
        if best is None or exp > best[1]:
            best, mark = (tp, exp), ""
        print(f"{tp:6.2f} {wr:7.1f}% {exp:+9.3f} {tot:+10.1f}")
    print(f"\nлучший тейк по матожиданию: {best[0]:.2f}R (E[R] {best[1]:+.3f}) · "
          f"сейчас стоит {rr:.1f}R")
    print("ВНИМАНИЕ: это подгонка под уже известную историю. Проверять только "
          "на отдельном периоде, иначе получится очередной «winrate 84%».")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--min-score", type=float, default=None,
                    help="по умолчанию берётся из настроек стратегии")
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
        ms = args.min_score if args.min_score is not None else st["min_score"]
        rr = st["risk_reward"]
        print(f"Порог оценки {ms}, R:R {rr}, стоп {st['sl_atr_multiple']}xATR\n")
        print(f"Загрузка свечей {args.tf}:")
        data = await _load(db, instruments, args.tf, args.bars)
    finally:
        db.close()

    if not data:
        print("\nНет реальных данных.")
        return

    params = {**DEFAULT_PARAMS, "min_score": ms, "risk_reward": rr,
              "sl_atr_multiple": st["sl_atr_multiple"], "bars": args.bars}
    rows: list[dict[str, Any]] = []
    for sym, candles in data.items():
        rows.extend(_excursions(candles, sym, params))

    print(f"\n{'='*60}\nХОД ЦЕНЫ ВНУТРИ СДЕЛКИ · {args.tf}\n{'='*60}")
    _report(rows, rr)


if __name__ == "__main__":
    asyncio.run(main())
