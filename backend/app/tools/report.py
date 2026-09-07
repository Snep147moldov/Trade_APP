"""Полная сводка состояния: настройки, счёт, сигналы, исполнение, аномалии.

Один запуск вместо десятка разовых SQL-запросов. Считает в R-мультипликаторах
(mt5_pnl / risk_amount), а не в евро: риск на сделку менялся в разы, и средние
в евро смешивают позиции разного размера.

Отделяет НАШИ сделки от чужих: на счёте торгует ещё кто-то (ордера с пустым
комментарием), и без фильтра по «Codnixy #id» статистика мешает две стратегии.

Запуск:
    docker compose exec -T backend python3 -m app.tools.report
    docker compose exec -T backend python3 -m app.tools.report --since 2026-08-21
"""

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Signal
from ..services import mt5 as mt5_svc
from ..services.runtime import get_app_config, get_credentials
from ..services.settings import get_settings


def _rstats(rows: list[tuple[float, float]]) -> dict[str, Any]:
    """rows = [(mt5_pnl, risk_amount)] -> статистика в R."""
    R = [p / r for p, r in rows if r]
    if not R:
        return {"n": 0}
    w = [x for x in R if x > 0.1]
    z = [x for x in R if -0.1 <= x <= 0.1]
    l = [x for x in R if x < -0.1]
    gw, gl = sum(w), -sum(l)
    return {
        "n": len(R), "wr": 100.0 * len(w) / len(R),
        "exp": sum(R) / len(R), "total": sum(R),
        "avg_win": (sum(w) / len(w)) if w else 0.0,
        "avg_loss": (sum(l) / len(l)) if l else 0.0,
        "zeros": len(z),
        "pf": (gw / gl) if gl > 0 else None,
    }


def _fmt(s: dict[str, Any]) -> str:
    if not s.get("n"):
        return "нет сделок"
    pf = s["pf"]
    return (f"{s['n']:4} сд. · WR {s['wr']:5.1f}% · E[R] {s['exp']:+6.3f} · "
            f"сумма {s['total']:+7.1f}R · выигрыш {s['avg_win']:+5.2f}R · "
            f"убыток {s['avg_loss']:+5.2f}R · PF "
            f"{(f'{pf:.2f}' if pf else '-')}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-21",
                    help="дата в формате ГГГГ-ММ-ДД")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        st, cfg, creds = get_settings(db), get_app_config(db), get_credentials(db)

        print("=" * 78)
        print(f"СВОДКА С {args.since}")
        print("=" * 78)

        print("\n--- НАСТРОЙКИ ---")
        for k in ("factor_signs", "min_score", "sl_atr_multiple", "risk_reward",
                  "expiry_bars", "ai_weight", "risk_per_trade_pct",
                  "blocked_hours_utc", "trend_hours_utc",
                  "daily_cutoff_hour", "quiet_resume_hour",
                  "max_open_risk_pct", "max_currency_risk_pct",
                  "max_risk_overshoot", "blocked_instruments"):
            print(f"  {k:24} {st.get(k)}")
        for k in ("autotrade_enabled", "autoscan_enabled", "autotrade_max_positions",
                  "autotrade_risk_sizing", "autotrade_orders_per_signal",
                  "autotrade_watchlist_auto", "telegram_confirm_required"):
            print(f"  {k:24} {cfg.get(k)}")
        print(f"  {'watchlist':24} {len(cfg.get('watchlist') or [])} пар")
        print(f"  {'счёт':24} {creds.get('mt5_server')} / {creds.get('mt5_login')}")

        print("\n--- СЧЁТ У БРОКЕРА ---")
        info = await mt5_svc.account_information(db)
        acc = info.get("account", {}) if info.get("ok") else {}
        print(f"  баланс {acc.get('balance')} {acc.get('currency')} · "
              f"эквити {acc.get('equity')}")
        pos = await mt5_svc.positions(db)
        ps = pos.get("positions", []) if pos.get("ok") else []
        print(f"  открыто позиций: {len(ps)}"
              + ("" if pos.get("ok") else f"  ОШИБКА: {pos.get('error')}"))
        for p in ps:
            print(f"    {p.get('symbol'):9} {p.get('volume')} лот · "
                  f"{float(p.get('profit') or 0):+7.2f} · "
                  f"'{p.get('comment') or ''}'")

        # --- фид: движок строит уровни по свечам провайдера. Когда тот молчит,
        # get_candles отдаёт встроенный симулятор (синусы вокруг base_price из
        # каталога), и сигнал уходит брокеру со стопами, не связанными с рынком.
        print("\n--- ФИД ДАННЫХ ---")
        from ..services.candles import active_provider, get_candles, is_simulated

        print(f"  провайдер: {active_provider(creds)}")
        probe = (list(cfg.get("watchlist") or []) or ["EUR_USD"])[:3]
        for sym in probe:
            try:
                cs = await get_candles(creds, sym, "1h", 60)
            except Exception as exc:
                print(f"    {sym:9} ОШИБКА: {type(exc).__name__}")
                continue
            if is_simulated(cs):
                print(f"    {sym:9} СИНТЕТИКА — сигналы по нему заблокированы")
            else:
                age = (datetime.now(timezone.utc).timestamp() - cs[-1]["time"]) / 60
                print(f"    {sym:9} рынок · {cs[-1]['close']} · "
                      f"последняя свеча {age:.0f} мин назад")

        rows = db.scalars(select(Signal).where(
            Signal.created_at >= args.since).order_by(Signal.id)).all()
        print(f"\n--- СИГНАЛЫ: {len(rows)} ---")
        by_state: dict[str, int] = defaultdict(int)
        for s in rows:
            by_state[s.confirm_state or "?"] += 1
        for k, v in sorted(by_state.items(), key=lambda x: -x[1]):
            print(f"  {k:14} {v}")
        sent = [s for s in rows if (s.mt5_orders or 0) > 0]
        print(f"  дошли до брокера: {len(sent)} из {len(rows)}")

        closed = [s for s in sent if s.mt5_pnl is not None and s.risk_amount]
        print("\n--- РЕЗУЛЬТАТ (наши сделки, в R) ---")
        print("  " + _fmt(_rstats([(s.mt5_pnl, s.risk_amount) for s in closed])))
        print("  цель по бэктесту: E[R] +0.146 · WR 42.7% · PF 1.26")

        if closed:
            print("\n--- ПО ИНСТРУМЕНТАМ ---")
            g: dict[str, list] = defaultdict(list)
            for s in closed:
                g[s.instrument].append((s.mt5_pnl, s.risk_amount))
            for k, v in sorted(g.items(),
                               key=lambda kv: -_rstats(kv[1])["total"]):
                print(f"  {k:9} {_fmt(_rstats(v))}")

            # мажор/кросс: у кросса тот же стоп в пипсах, но спред кратно
            # шире, а бэктест считал спред одинаковым (1.0 пункт) для всех пар
            print("\n--- ПО ТИПУ ПАРЫ ---")
            g = defaultdict(list)
            for s in closed:
                parts = s.instrument.split("_")
                kind = ("металл" if parts[0] in ("XAU", "XAG", "XPT")
                        else "мажор (с USD)" if "USD" in parts
                        else "кросс (без USD)")
                g[kind].append((s.mt5_pnl, s.risk_amount))
            for k, v in sorted(g.items()):
                print(f"  {k:16} {_fmt(_rstats(v))}")

            print("\n--- ПО ТАЙМФРЕЙМАМ ---")
            g = defaultdict(list)
            for s in closed:
                g[s.timeframe].append((s.mt5_pnl, s.risk_amount))
            for k, v in sorted(g.items()):
                print(f"  {k:9} {_fmt(_rstats(v))}")

            print("\n--- ПО ЧАСУ ВХОДА (UTC / Бухарест) ---")
            g = defaultdict(list)
            for s in closed:
                t = s.created_at
                h = (t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t).hour
                g[h].append((s.mt5_pnl, s.risk_amount))
            for h in sorted(g):
                blocked = " [ЗАБЛОКИРОВАН]" if h in (
                    st.get("blocked_hours_utc") or []) else ""
                print(f"  {h:02d}/{(h+3)%24:02d}  {_fmt(_rstats(g[h]))}{blocked}")

        # ---------- реальный спред брокера против нашего стопа
        # risk-менеджер до сих пор берёт спред из каталога, где на каждую
        # валютную пару записано одно и то же 0.02% — порог max_cost_ratio
        # поэтому не отличает EUR/USD от NZD/CAD и не срабатывает никогда.
        # Здесь спред спрашивается у брокера и сравнивается с НАШИМ средним
        # стопом по этой паре: столько процентов от R уходит в издержки.
        from ..services.candles import pip_size

        market: dict[str, float] = {}
        stop_pips: dict[str, list[float]] = defaultdict(list)
        for s in rows:
            p = pip_size(s.instrument)
            if s.entry and s.stop_loss and p:
                stop_pips[s.instrument].append(abs(s.entry - s.stop_loss) / p)
        if stop_pips:
            print("\n--- СПРЕД БРОКЕРА ПРОТИВ НАШЕГО СТОПА ---")
            print(f"  {'пара':9} {'спред п.':>9} {'наш стоп п.':>12} "
                  f"{'% от R':>8} {'провайдер-брокер':>18} {'% стопа':>9}")
            costs: list[tuple[float, str, float, float, float]] = []
            for sym in sorted(stop_pips):
                pr = await mt5_svc.symbol_price(db, sym)
                if not pr.get("ok"):
                    print(f"  {sym:9} нет цены: {pr.get('error')}")
                    continue
                mid = (pr["bid"] + pr["ask"]) / 2.0
                market[sym] = mid
                sp = pr["spread"] / pip_size(sym)
                avg = sum(stop_pips[sym]) / len(stop_pips[sym])
                # Расхождение ленты с брокером. Уровни сигнала строятся по
                # закрытию свечи ПРОВАЙДЕРА, а ордер исполняется по цене
                # БРОКЕРА. Пока расхождение мало по сравнению со стопом, это
                # неважно. Если по кроссам оно сопоставимо со стопом, то вход,
                # стоп и цель оказываются сдвинуты относительно того рынка, на
                # котором сделка живёт, и результат перестаёт зависеть от
                # формулы. Мажоры служат контролем: движение цены за время
                # между свечой и котировкой действует на всех одинаково.
                drift = float("nan")
                try:
                    cs = await get_candles(creds, sym, "1h", 5)
                    if cs and not is_simulated(cs):
                        drift = abs(cs[-1]["close"] - mid) / pip_size(sym)
                except Exception:
                    pass
                costs.append((200.0 * sp / avg if avg else 0.0, sym, sp, avg, drift))
            for ratio, sym, sp, avg, drift in sorted(costs, reverse=True):
                d = "     —" if drift != drift else f"{drift:6.1f} п."
                dp = "" if drift != drift or not avg else f"{100*drift/avg:8.0f}%"
                mark = "  <--" if drift == drift and avg and drift > 0.5 * avg else ""
                print(f"  {sym:9} {sp:9.2f} {avg:12.1f} {ratio:7.1f}% "
                      f"{d:>18} {dp:>9}{mark}")

        # ---------- сигналы, построенные на встроенном симуляторе
        # Симулятор — сумма синусов вокруг base_price из каталога, и уходит от
        # него не дальше 0.85% (trend 0.0077 + noise 0.0006). Значит сигнал,
        # чья цена входа попала в эту полосу, построен на симуляторе — при
        # условии, что настоящий рынок стоит в стороне. Проверяем только пары,
        # где каталог и брокер расходятся больше чем на 1.5%: там ответ
        # однозначный.
        from ..catalog import meta as _meta

        SIM_BAND = 0.0085
        rowsN: list[tuple[float, float]] = []
        rowsR: list[tuple[float, float]] = []
        diag: list[tuple[str, float, float, float, int, int]] = []
        for sym, px in sorted(market.items()):
            base = (_meta(sym) or {}).get("base_price")
            if not base or not px:
                continue
            drift = abs(base / px - 1.0)
            if drift <= 0.015:
                continue  # каталог совпал с рынком — отличить нельзя
            insiders = 0
            total = 0
            for s in rows:
                if s.instrument != sym or not s.entry:
                    continue
                total += 1
                inside = abs(s.entry / base - 1.0) <= SIM_BAND
                if inside:
                    insiders += 1
                if s.mt5_pnl is not None and s.risk_amount:
                    (rowsN if inside else rowsR).append((s.mt5_pnl, s.risk_amount))
            if total:
                diag.append((sym, base, px, drift * 100, insiders, total))
        if diag:
            print("\n--- СИГНАЛЫ, ПОСТРОЕННЫЕ НА СИМУЛЯТОРЕ ---")
            print("  симулятор не отходит от base_price дальше 0.85%;")
            print("  сравниваем с ценой брокера там, где каталог устарел\n")
            print(f"  {'пара':9} {'base_price':>11} {'рынок':>11} "
                  f"{'расхожд.':>9} {'в полосе':>10}")
            for sym, base, px, drift, ins, tot in sorted(
                    diag, key=lambda d: -d[4]):
                print(f"  {sym:9} {base:11.4f} {px:11.4f} {drift:8.1f}% "
                      f"{ins:5} из {tot}")
            print()
            print("  на симуляторе: " + _fmt(_rstats(rowsN)))
            print("  на рынке:      " + _fmt(_rstats(rowsR)))

        # ---------- аномалии
        print("\n--- ПРОБЛЕМЫ ---")
        problems = 0

        never = [s for s in rows
                 if (s.confirm_state or "not_required") in ("not_required", "accepted")
                 and not (s.mt5_orders or 0)
                 and s.status != "open"]
        if never:
            problems += 1
            print(f"  {len(never)} сигналов были РАЗРЕШЕНЫ, но ордера не ушли:")
            for s in never[:8]:
                print(f"    #{s.id} {s.instrument} {s.timeframe} "
                      f"{s.confirm_state} -> {s.status}")

        stuck = [s for s in rows if s.status == "open" and s.mt5_pnl is not None]
        if stuck:
            problems += 1
            print(f"  {len(stuck)} сигналов висят 'open', хотя брокер уже заплатил:")
            for s in stuck[:8]:
                print(f"    #{s.id} {s.instrument} mt5_pnl={s.mt5_pnl}")

        # расхождение модели приложения с деньгами брокера
        diverged = [s for s in closed
                    if s.pnl_money is not None
                    and abs(s.pnl_money - s.mt5_pnl) > max(1.0, 0.25 * abs(s.mt5_pnl))]
        if diverged:
            problems += 1
            print(f"  {len(diverged)} сделок: расчёт приложения != деньги брокера:")
            for s in diverged[:8]:
                print(f"    #{s.id} {s.instrument} app={s.pnl_money:+.2f} "
                      f"брокер={s.mt5_pnl:+.2f}")

        big = [s for s in closed if s.mt5_pnl / s.risk_amount < -1.3]
        if big:
            problems += 1
            print(f"  {len(big)} убытков БОЛЬШЕ стопа (хуже -1.3R):")
            for s in big[:8]:
                print(f"    #{s.id} {s.instrument} "
                      f"{s.mt5_pnl / s.risk_amount:+.2f}R орд={s.mt5_orders}")

        if not problems:
            print("  не найдено")

        # ---------- чужие сделки
        print("\n--- ЧУЖАЯ ТОРГОВЛЯ НА СЧЁТЕ ---")
        now = datetime.now(timezone.utc)
        h = await mt5_svc.history_deals(
            db, (now - timedelta(days=14)).isoformat(), now.isoformat())
        if h.get("ok"):
            ours = other = 0.0
            n_ours = n_other = 0
            for d in h.get("deals", []):
                if d.get("entryType") != "DEAL_ENTRY_OUT":
                    continue
                v = (float(d.get("profit") or 0) + float(d.get("commission") or 0)
                     + float(d.get("swap") or 0))
                if "Codnixy" in (d.get("comment") or d.get("brokerComment") or ""):
                    ours += v
                    n_ours += 1
                else:
                    other += v
                    n_other += 1
            print(f"  наши (Codnixy): {n_ours} сделок, {ours:+.2f} EUR")
            print(f"  чужие:          {n_other} сделок, {other:+.2f} EUR")
        else:
            print(f"  история недоступна: {h.get('error')}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
