"""Advanced position size calculator (all money in EUR).

units = (balance * risk% - commission) / ((|entry - SL| + spread) * eur_per_quote)

Volatility guard: when the stop is tighter than 0.8 * ATR14, the instrument's
noise alone can hit it — the calculator flags it and suggests an ATR-based
stop instead.
"""

from typing import Any

from ..services.candles import pip_size, price_precision


def position_size(
    *,
    instrument: str,
    balance_eur: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    leverage: float = 30.0,
    commission_eur: float = 0.0,
    spread_pips: float = 0.0,
    atr: float | None = None,
    eur_per_quote: float = 1.0,
    risk_reward: float | None = None,
) -> dict[str, Any]:
    pip = pip_size(instrument)
    prec = price_precision(instrument)
    sl_distance = abs(entry - stop_loss)
    warnings: list[str] = []

    if balance_eur <= 0 or risk_pct <= 0 or entry <= 0 or sl_distance <= 0:
        return {"ok": False, "error": "проверьте вход: баланс, риск %, цены входа и стопа"}

    spread_price = spread_pips * pip
    effective_distance = sl_distance + spread_price

    risk_eur = balance_eur * risk_pct / 100.0
    risk_after_costs = max(risk_eur - commission_eur, 0.0)
    if risk_after_costs <= 0:
        return {"ok": False, "error": "комиссия съедает весь допустимый риск"}

    units = risk_after_costs / (effective_distance * max(eur_per_quote, 1e-12))
    notional_eur = units * entry * eur_per_quote
    margin_eur = notional_eur / max(leverage, 1.0)
    max_loss_eur = risk_after_costs + commission_eur

    if margin_eur > balance_eur:
        warnings.append(
            f"требуемая маржа {margin_eur:.0f}€ превышает баланс — уменьшите размер или плечо"
        )
    if risk_pct > 2.0:
        warnings.append(f"риск {risk_pct:.1f}% на сделку выше рекомендуемых 1–2%")
    if atr and sl_distance < 0.8 * atr:
        warnings.append(
            f"стоп ({sl_distance:.{prec}f}) уже 0.8×ATR14 ({atr:.{prec}f}) — "
            f"рыночный шум может выбить позицию; рассмотрите SL ≥ 1.5×ATR"
        )

    out: dict[str, Any] = {
        "ok": True,
        "units": round(units),
        "lots": round(units / 100_000, 4),  # standard forex lot
        "risk_eur": round(risk_eur, 2),
        "max_loss_eur": round(max_loss_eur, 2),
        "risk_pct": round(risk_pct, 2),
        "margin_eur": round(margin_eur, 2),
        "notional_eur": round(notional_eur, 2),
        "sl_distance": round(sl_distance, prec),
        "sl_pips": round(sl_distance / pip, 1),
        "spread_cost_eur": round(units * spread_price * eur_per_quote, 2),
        "commission_eur": round(commission_eur, 2),
        "warnings": warnings,
    }
    if risk_reward and risk_reward > 0:
        out["take_profit_distance"] = round(sl_distance * risk_reward, prec)
        out["potential_profit_eur"] = round(risk_after_costs * risk_reward, 2)
    return out
