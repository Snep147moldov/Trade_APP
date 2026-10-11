"""Shared outcome definitions; never infer a win from an exit label or pips."""

import math
from typing import Any

CLOSED = ("hit_tp", "hit_sl", "expired")


def wilson_interval(wins: int, total: int) -> list[float] | None:
    """95% binomial interval in percent (independent-trade approximation)."""
    if not total:
        return None
    z = 1.959963984540054
    p = wins / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denom
    return [round(100 * (center - half), 2), round(100 * (center + half), 2)]


def trade_metrics(trades: list[dict]) -> dict[str, Any]:
    """Net EUR wins/expectancy; `r` is net EUR divided by initial EUR risk.

    Unrounded amounts determine the classification. Zero outcomes remain in
    the denominator and have a separate count. PF in R is explicitly separate
    from PF in money because compounding changes position sizes.
    """
    n = len(trades)
    money = [float(t["pnl_eur"]) for t in trades]
    rs = [float(t["r"]) for t in trades]
    wins = sum(x > 0 for x in money)
    losses = sum(x < 0 for x in money)
    gw = math.fsum(x for x in money if x > 0)
    gl = -math.fsum(x for x in money if x < 0)
    rw = math.fsum(x for x in rs if x > 0)
    rl = -math.fsum(x for x in rs if x < 0)
    mean = math.fsum(rs) / n if n else None
    std = math.sqrt(math.fsum((x - mean)**2 for x in rs) / (n - 1)) if n > 1 else 0
    return {
        "trades": n, "wins": wins, "losses": losses,
        "breakevens": n - wins - losses,
        "win_rate": round(100 * wins / n, 2) if n else None,
        "win_rate_ci95": wilson_interval(wins, n),
        "profit_factor": round(gw / gl, 4) if gl > 0 else None,
        "profit_factor_r": round(rw / rl, 4) if rl > 0 else None,
        "profit_factor_status": "finite" if gl > 0 else ("no_losses" if gw > 0 else "no_pnl"),
        "expectancy_eur": math.fsum(money) / n if n else None,
        "expectancy_r": mean, "total_r": math.fsum(rs),
        "sharpe_per_trade": mean / std if std > 0 else None,
        "avg_win_eur": gw / wins if wins else None,
        "avg_loss_eur": gl / losses if losses else None,
    }


def net_pnl(signal) -> float | None:
    """Broker settlement is authoritative, including fees and partial fills."""
    value = signal.mt5_pnl if (signal.mt5_orders or 0) > 0 else signal.pnl_money
    return float(value) if value is not None and math.isfinite(value) else None


def closed_sample(signals: list) -> tuple[list, str]:
    """Use broker trades when present; paper trades form a separate population.

    An unreported execution is missing data, never a zero-return trade.
    """
    broker = any((s.mt5_orders or 0) > 0 for s in signals)
    rows = [s for s in signals if s.status in CLOSED
            and ((s.mt5_orders or 0) > 0) == broker and net_pnl(s) is not None]
    return rows, "broker" if broker else "paper"
