"""Свести список открытых сигналов приложения с позициями у брокера.

07.09 в приложении висело 17 «открытых» позиций, у брокера — три. Остальные
четырнадцать до брокера не дошли: часть отклонил риск-менеджер по размеру лота,
часть осталась от эпохи, когда провайдер молча отдавал симулятор. Одна из них,
EUR/USD 40m со входом 1.07923 при рынке 1.16256, показывала +67.93 EUR
несуществующей прибыли и тянула за собой всю статистику.

Риск-гейт такие сигналы уже не считает (только mt5_orders > 0), но они остаются
в списке, в отчётах и в расчёте P&L.

Правила простые и намеренно осторожные:
  - сигнал с живой позицией у брокера НЕ трогаем ни при каких условиях;
  - сигнал без ордеров закрываем как expired с нулевым P&L — денег по нему
    не было, значит и результата быть не может;
  - вход в полосе +-0.85% от base_price при разошедшемся рынке помечаем
    отдельно: это цена симулятора, а не рынка.

По умолчанию ничего не меняет — только показывает. Менять с --apply.

Запуск:
    docker compose exec -T backend python3 -m app.tools.sync
    docker compose exec -T backend python3 -m app.tools.sync --apply
"""

import argparse
import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy import select

from ..catalog import meta
from ..database import SessionLocal
from ..models import Signal
from ..services import mt5 as mt5_svc
from ..services.runtime import get_credentials

SIM_BAND = 0.0085


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="действительно закрыть повисшие сигналы")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        creds = get_credentials(db)
        positions: list[dict] = []
        if mt5_svc.is_configured(creds):
            p = await mt5_svc.positions(db)
            if not p.get("ok"):
                print(f"брокер недоступен: {p.get('error')} — без списка позиций "
                      "сверять нечего, ничего не меняем")
                return
            positions = p["positions"]
        else:
            print("MT5 не подключён — сверять не с чем")
            return

        open_sigs = db.scalars(
            select(Signal).where(Signal.status == "open").order_by(Signal.id)).all()

        def broker_rows(sig_id: int) -> list[dict]:
            pat = re.compile(rf"#{sig_id}(\D|$)")
            return [x for x in positions if pat.search(x.get("comment") or "")]

        print(f"у брокера позиций: {len(positions)}")
        for x in positions:
            print(f"    {x.get('symbol'):9} {x.get('type'):5} {x.get('volume')} "
                  f"лот · {float(x.get('profit') or 0):+.2f} · "
                  f"'{x.get('comment') or ''}'")
        print(f"\nв приложении открытых сигналов: {len(open_sigs)}\n")

        live: list[Signal] = []
        stale: list[tuple[Signal, str]] = []
        for sig in open_sigs:
            if broker_rows(sig.id):
                live.append(sig)
                continue
            base = (meta(sig.instrument) or {}).get("base_price")
            why = "ордера не уходили"
            if base and sig.entry and abs(sig.entry / base - 1.0) <= SIM_BAND:
                why = f"вход {sig.entry} — цена симулятора (base {base})"
            stale.append((sig, why))

        print(f"{'':4}{'сигнал':>7}  {'инструмент':<10} {'тф':<5} {'состояние'}")
        for sig in live:
            print(f"    {('#' + str(sig.id)):>7}  {sig.instrument:<10} "
                  f"{sig.timeframe:<5} позиция у брокера ЖИВА — не трогаем")
        for sig, why in stale:
            print(f"    {('#' + str(sig.id)):>7}  {sig.instrument:<10} "
                  f"{sig.timeframe:<5} {why}")

        print(f"\nживых {len(live)} · повисших {len(stale)}")
        if not stale:
            print("сводить нечего")
            return

        phantom = sum(s.pnl_money or 0.0 for s, _ in stale)
        print(f"эти сигналы показывают {phantom:+.2f} EUR несуществующего P&L")

        if not args.apply:
            print("\nничего не изменено. Повторить с --apply, чтобы закрыть их "
                  "как expired с нулевым результатом.")
            return

        now = datetime.now(timezone.utc)
        for sig, why in stale:
            sig.status = "expired"
            sig.resolved_at = now
            sig.pnl_money = 0.0
            sig.pnl_pips = 0.0
            sig.mt5_pnl = None
            sig.notes = ((sig.notes or "") +
                         f" [сверка {now:%d.%m}] снят: {why}").strip()
        db.commit()
        print(f"\nзакрыто {len(stale)} сигналов с нулевым P&L")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
