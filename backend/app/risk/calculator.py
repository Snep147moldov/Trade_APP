"""Advanced position size calculator (all money in EUR).

units = (balance * risk% - commission) / ((|entry - SL| + spread) * eur_per_quote)

Volatility guard: when the stop is tighter than 0.8 * ATR14, the instrument's
noise alone can hit it — the calculator flags it and suggests an ATR-based
stop instead.
"""

import math
from typing import Any

from ..services.candles import pip_size, price_precision
from ..services.mt5 import contract_size
from ..i18n import t


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

    if (not all(math.isfinite(v) for v in (balance_eur, risk_pct, entry, stop_loss,
                                          leverage, commission_eur, spread_pips, eur_per_quote))
            or balance_eur <= 0 or not 0 < risk_pct <= 100 or entry <= 0
            or stop_loss <= 0 or sl_distance <= 0 or eur_per_quote <= 0
            or commission_eur < 0 or spread_pips < 0 or leverage <= 0):
        return {"ok": False, "error": t("проверьте вход: баланс, риск %, цены входа и стопа")}

    spread_price = spread_pips * pip
    effective_distance = sl_distance + spread_price

    risk_eur = balance_eur * risk_pct / 100.0
    risk_after_costs = max(risk_eur - commission_eur, 0.0)
    if risk_after_costs <= 0:
        return {"ok": False, "error": t("комиссия съедает весь допустимый риск")}

    units = risk_after_costs / (effective_distance * max(eur_per_quote, 1e-12))
    notional_eur = units * entry * eur_per_quote
    margin_eur = notional_eur / max(leverage, 1.0)
    max_loss_eur = risk_after_costs + commission_eur

    if margin_eur > balance_eur:
        warnings.append(
            t("требуемая маржа {0}€ превышает баланс — уменьшите размер или плечо", f"{margin_eur:.0f}")
        )
    if risk_pct > 2.0:
        warnings.append(t("риск {0}% на сделку выше рекомендуемых 1–2%", f"{risk_pct:.1f}"))
    if atr and sl_distance < 0.8 * atr:
        warnings.append(
            t("стоп ({0}) уже 0.8×ATR14 ({1}) — рыночный шум может выбить позицию; рассмотрите SL ≥ 1.5×ATR", f"{sl_distance:.{prec}f}", f"{atr:.{prec}f}")
        )

    out: dict[str, Any] = {
        "ok": True,
        "units": round(units, 8),
        "lots": round(units / contract_size(instrument), 6),
        "contract_size_assumed": contract_size(instrument),
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
        out["potential_profit_eur"] = round(units * (sl_distance * risk_reward - spread_price) * eur_per_quote - commission_eur, 2)
    return out
