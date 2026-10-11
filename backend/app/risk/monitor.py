"""Интеллектуальный риск-монитор: следит за открытыми позициями и портфелем,
каждое предупреждение сопровождается корректирующим действием.

Checks: per-position risk vs plan, floating loss beyond plan, poor R:R,
portfolio exposure, correlated positions (shared currencies, same direction),
daily-limit proximity. Deterministic — no AI calls.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import currencies_of, meta as catalog_meta
from ..models import Signal
from ..services.candles import pip_size
from ..services.market import forex_minutes_to_close
from ..services.quotes import get_quotes
from ..services.settings import get_settings
from . import limits as risk_limits
from ..i18n import t

SEV = {"info": 0, "warning": 1, "critical": 2}


def _alert(severity: str, title: str, detail: str, action: str,
           instrument: str = "") -> dict[str, Any]:
    return {"severity": severity, "title": title, "detail": detail,
            "action": action, "instrument": instrument}


async def portfolio_monitor(db: Session) -> dict[str, Any]:
    settings = get_settings(db)
    equity = settings["account_equity"]
    open_sigs = db.scalars(select(Signal).where(Signal.status == "open")).all()
    state = risk_limits.day_state(db, settings)
    alerts: list[dict[str, Any]] = []

    quotes = await get_quotes(db, [s.instrument for s in open_sigs])

    positions = []
    total_float = 0.0
    for s in open_sigs:
        q = quotes.get(s.instrument)
        price = q["price"] if q else None
        floating = None
        r_now = None
        if price and s.risk_amount:
            risk_dist = abs(s.entry - s.stop_loss)
            side = 1.0 if s.direction == "BUY" else -1.0
            r_now = side * (price - s.entry) / risk_dist if risk_dist > 0 else 0.0
            floating = round(r_now * s.risk_amount, 2)
            total_float += floating

        planned_pct = settings["risk_per_trade_pct"]
        actual_pct = (s.risk_amount or 0) / equity * 100 if equity else 0
        if actual_pct > planned_pct * 1.5:
            alerts.append(_alert(
                "warning", t("Риск позиции выше плана — {0}", f"{s.instrument}"),
                t("Сигнал #{0}: под риском {1}% капитала при плане {2}%.", f"{s.id}", f"{actual_pct:.1f}", f"{planned_pct:.1f}"),
                t("Сократите размер позиции или закройте часть, чтобы вернуться к плану."),
                s.instrument))
        if s.risk_reward < 1.0:
            alerts.append(_alert(
                "warning", t("Слабое соотношение R:R — {0}", f"{s.instrument}"),
                t("Сигнал #{0}: риск/прибыль {1} < 1.0.", f"{s.id}", f"{s.risk_reward:.2f}"),
                t("Пересмотрите тейк-профит или откажитесь от таких сделок: матожидание отрицательно даже при винрейте 50%."),
                s.instrument))
        if r_now is not None and r_now < -1.05:
            alerts.append(_alert(
                "critical", t("Позиция за стопом — {0}", f"{s.instrument}"),
                t("Сигнал #{0}: текущий убыток {1}R превышает план (−1R). Возможен гэп или пропуск стопа.", f"{s.id}", f"{r_now:.2f}"),
                t("Закройте позицию немедленно — план риска уже нарушен."),
                s.instrument))

        positions.append({
            "id": s.id, "instrument": s.instrument, "direction": s.direction,
            "timeframe": s.timeframe, "entry": s.entry,
            "stop_loss": s.current_sl or s.stop_loss,
            "take_profit": s.take_profit,
            "risk_amount": s.risk_amount, "price": price,
            "floating_eur": floating,
            "r_now": round(r_now, 2) if r_now is not None else None,
            "be_moved": bool(s.be_moved), "partial_taken": bool(s.partial_taken),
            "sl_pips": round(abs(s.entry - (s.current_sl or s.stop_loss))
                             / pip_size(s.instrument), 1),
        })

    # portfolio-level exposure
    if state["open_risk_pct"] > settings["max_open_risk_pct"] * 0.8 > 0:
        sev = "critical" if state["open_risk_pct"] >= settings["max_open_risk_pct"] else "warning"
        alerts.append(_alert(
            sev, t("Высокая суммарная экспозиция"),
            t("Открытый риск {0}% капитала (лимит {1}%).", f"{state['open_risk_pct']:.1f}", f"{settings['max_open_risk_pct']:.0f}"),
            t("Не открывайте новые позиции; закройте слабейшую, чтобы снизить экспозицию.")))

    # correlated positions: same currency on the same side
    ccy_dir: dict[tuple[str, str], list[str]] = {}
    for s in open_sigs:
        for c in currencies_of(s.instrument):
            base = s.instrument.split("_")[0]
            long_ccy = (s.direction == "BUY") == (c == base)
            key = (c, "long" if long_ccy else "short")
            ccy_dir.setdefault(key, []).append(s.instrument)
    for (ccy, side), instruments in ccy_dir.items():
        if len(instruments) >= 2:
            alerts.append(_alert(
                "warning", t("Коррелированные позиции по {0}", f"{ccy}"),
                t("{0} позиции в одну сторону ({1}) по {2}: {3}. Фактический риск складывается.", f"{len(instruments)}", f"{side}", f"{ccy}", f"{', '.join(instruments)}"),
                t("Считайте эти позиции одной сделкой: суммарный риск не должен превышать разовый лимит на сделку.")))

    # weekend gap risk: non-crypto positions held into the Friday close
    non_crypto = [s for s in open_sigs
                  if (catalog_meta(s.instrument) or {}).get("category") != "crypto"]
    if non_crypto:
        mins = forex_minutes_to_close()
        if mins is None:
            alerts.append(_alert(
                "info", t("Рынок закрыт (выходные)"),
                t("{0} позиций ждут открытия рынка. Стопы не исполняются, пока рынок закрыт — воскресный гэп может открыться за стоп-лоссом.", f"{len(non_crypto)}"),
                t("Проверьте позиции сразу после открытия (воскресенье ~21:00 UTC).")))
        elif mins <= 240:
            alerts.append(_alert(
                "warning" if mins > 60 else "critical",
                t("Рынок закрывается через {0} ч", f"{mins/60:.1f}"),
                t("{0} позиций останутся открытыми через выходные: {1}. Гэп в воскресенье может перескочить стоп-лосс (исполнение по худшей цене).", f"{len(non_crypto)}", f"{', '.join(s.instrument for s in non_crypto[:5])}"),
                t("Закройте или сократите позиции до пятницы 21:00 UTC, либо примите риск гэпа осознанно.")))

    # daily limits proximity / breaches
    for msg in state["warnings"]:
        alerts.append(_alert("warning", t("Приближение к лимиту"), msg,
                             t("Снизьте темп: следующая сделка только по идеальному сетапу.")))
    for msg in state["blocked"]:
        alerts.append(_alert("critical", t("Лимит достигнут — торговля остановлена"), msg,
                             t("Новые сигналы блокируются до конца периода. Отдохните и разберите сегодняшние сделки в журнале.")))

    alerts.sort(key=lambda a: -SEV.get(a["severity"], 0))
    return {
        "positions": positions,
        "alerts": alerts,
        "limits": state,
        "floating_eur": round(total_float, 2),
        "equity": equity,
    }
