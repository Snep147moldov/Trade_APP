"""Бэктест того же детерминированного движка на исторических свечах.

Honesty rules:
  - AI terms are forced to 0 (no historical sentiment vectors exist) and the
    higher-timeframe confirmation factor is dropped (single-TF data) — the
    backtest evaluates the single-timeframe *formula* part of the strategy;
  - entries pay spread + slippage, every trade pays a flat commission (EUR);
  - inside a candle the stop is checked before the take-profit;
  - a gap through the stop exits at the worse open price (through the TP —
    at the better one), matching live outcome tracking;
  - position sizing compounds on current equity, same as live risk manager.

Walk-forward: rolling train/test folds; min_score is re-optimized on each
train segment and evaluated out-of-sample on the next one.
"""

import time
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SONNET_MODEL
from ..indicators import core as ind
from ..models import BacktestRun
from ..services.candles import get_candles, pip_size
from ..services.runtime import get_credentials, log_usage
from ..signals.engine import ER_PERIOD, TSMOM_LOOKBACK, score_components

WARMUP = 60
EXPIRY_BARS = 96
MIN_SCORE_GRID = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]

DEFAULT_PARAMS = {
    "bars": 1500,
    "initial_equity": 10000.0,   # EUR
    "risk_per_trade_pct": 1.0,
    "min_score": 0.30,
    "min_adx": 18.0,
    "risk_reward": 1.8,
    "sl_atr_multiple": 1.5,
    "spread_pips": 1.0,
    "slippage_pips": 0.2,
    "commission_eur": 0.0,       # flat, per round-trip
    "cooldown_bars": 3,
}


def _precompute(candles: list[dict]) -> dict[str, np.ndarray]:
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    n = len(close)

    ema20 = ind.ema(close, 20)
    ema50 = ind.ema(close, 50)
    rsi14 = ind.rsi(close, 14)
    _, _, macd_hist = ind.macd(close)
    _, _, _, pct_b = ind.bollinger(close)
    atr14 = ind.atr(high, low, close, 14)
    stoch_k, stoch_d = ind.stochastic(high, low, close)
    adx14, _, _ = ind.adx(high, low, close)
    roc10 = ind.roc(close, 10)

    hurst = np.full(n, 0.5)
    for i in range(WARMUP, n):
        if i >= 101:
            hurst[i] = ind.hurst_exponent(close[:i + 1], window=100)

    er = np.zeros(n)
    er_sign = np.ones(n)
    for i in range(ER_PERIOD + 1, n):
        er[i] = ind.efficiency_ratio(close[:i + 1], ER_PERIOD)
        er_sign[i] = 1.0 if close[i] >= close[i - ER_PERIOD] else -1.0

    tsmom = np.zeros(n)
    tsmom[TSMOM_LOOKBACK:] = close[TSMOM_LOOKBACK:] - close[:-TSMOM_LOOKBACK]

    return {
        "close": close, "high": high, "low": low,
        "ema20": ema20, "ema50": ema50, "rsi14": rsi14, "macd_hist": macd_hist,
        "pct_b": pct_b, "atr14": atr14, "stoch_k": stoch_k, "stoch_d": stoch_d,
        "adx14": adx14, "roc10": roc10, "hurst": hurst,
        "er": er, "er_sign": er_sign, "tsmom": tsmom,
    }


def _snap(pre: dict[str, np.ndarray], i: int) -> dict[str, Any]:
    def v(key):
        x = pre[key][i]
        return None if np.isnan(x) else float(x)

    return {
        "close": float(pre["close"][i]),
        "ema20": v("ema20"), "ema50": v("ema50"), "rsi14": v("rsi14"),
        "macd_hist": v("macd_hist"), "pct_b": v("pct_b"), "atr14": v("atr14"),
        "stoch_k": v("stoch_k"), "stoch_d": v("stoch_d"), "adx14": v("adx14"),
        "roc10": v("roc10"), "hurst": float(pre["hurst"][i]),
        "er_signed": float(pre["er"][i] * pre["er_sign"][i]),
        "tsmom_return": float(pre["tsmom"][i]),
    }


def simulate(candles: list[dict], instrument: str,
             params: dict[str, Any]) -> dict[str, Any]:
    p = {**DEFAULT_PARAMS, **params}
    pip = pip_size(instrument)
    cost_price = (p["spread_pips"] + p["slippage_pips"]) * pip

    pre = _precompute(candles)
    n = len(candles)
    equity = float(p["initial_equity"])
    peak = equity
    max_dd = 0.0
    curve: list[dict] = []
    trades: list[dict] = []
    rs: list[float] = []

    open_pos: dict | None = None
    last_entry_bar = -10_000

    for i in range(WARMUP, n):
        c = candles[i]
        # ------------------------------ manage open position (SL first)
        if open_pos:
            is_buy = open_pos["direction"] == "BUY"
            hit_sl = c["low"] <= open_pos["sl"] if is_buy else c["high"] >= open_pos["sl"]
            hit_tp = c["high"] >= open_pos["tp"] if is_buy else c["low"] <= open_pos["tp"]
            exit_price = None
            status = None
            # a gap through the stop fills at the (worse) open; a gap through
            # the take-profit fills at the (better) open — same as live tracking
            if hit_sl:
                px = min(open_pos["sl"], c["open"]) if is_buy \
                    else max(open_pos["sl"], c["open"])
                exit_price, status = px, "hit_sl"
            elif hit_tp:
                px = max(open_pos["tp"], c["open"]) if is_buy \
                    else min(open_pos["tp"], c["open"])
                exit_price, status = px, "hit_tp"
            elif i - open_pos["bar"] >= EXPIRY_BARS:
                exit_price, status = c["close"], "expired"
            if exit_price is not None:
                side = 1.0 if is_buy else -1.0
                r = side * (exit_price - open_pos["entry"]) / open_pos["risk_dist"]
                pnl = r * open_pos["risk_eur"] - p["commission_eur"]
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0)
                rs.append(r)
                trades.append({
                    "entry_time": candles[open_pos["bar"]]["time"],
                    "exit_time": c["time"],
                    "direction": open_pos["direction"],
                    "entry": round(open_pos["entry"], 6),
                    "exit": round(exit_price, 6),
                    "sl": round(open_pos["sl"], 6), "tp": round(open_pos["tp"], 6),
                    "bars_held": i - open_pos["bar"],
                    "r": round(r, 3), "pnl_eur": round(pnl, 2),
                    "status": status, "score": open_pos["score"],
                    "equity_after": round(equity, 2),
                })
                curve.append({"time": c["time"], "value": round(equity, 2)})
                open_pos = None

        # --------------------------------------- entries (flat only)
        if open_pos or i - last_entry_bar < p["cooldown_bars"] or i >= n - 1:
            continue
        snap = _snap(pre, i)
        if snap["atr14"] is None or snap["ema20"] is None:
            continue
        _, _, score, _ = score_components(snap, 0.0, 0.0, p["min_adx"], ai_weight=0.0)
        if abs(score) < p["min_score"]:
            continue
        direction = "BUY" if score > 0 else "SELL"
        side = 1.0 if score > 0 else -1.0
        atr = snap["atr14"]
        entry = c["close"] + side * cost_price  # pay spread + slippage
        sl_dist = p["sl_atr_multiple"] * atr
        sl = entry - side * sl_dist
        tp = entry + side * sl_dist * p["risk_reward"]
        risk_eur = equity * p["risk_per_trade_pct"] / 100.0
        if risk_eur <= 0 or sl_dist <= 0:
            continue
        open_pos = {"bar": i, "direction": direction, "entry": entry, "sl": sl,
                    "tp": tp, "risk_dist": sl_dist, "risk_eur": risk_eur,
                    "score": round(score, 3)}
        last_entry_bar = i

    wins = [t for t in trades if t["pnl_eur"] > 0]
    losses = [t for t in trades if t["pnl_eur"] <= 0]
    gross_w = sum(t["pnl_eur"] for t in wins)
    gross_l = -sum(t["pnl_eur"] for t in losses)
    r_arr = np.array(rs) if rs else np.array([0.0])

    metrics = {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "profit_factor": round(gross_w / gross_l, 2) if gross_l > 0 else None,
        "expectancy_eur": round(sum(t["pnl_eur"] for t in trades) / len(trades), 2)
        if trades else None,
        "expectancy_r": round(float(r_arr.mean()), 3) if trades else None,
        "sharpe_per_trade": round(float(r_arr.mean() / r_arr.std()), 2)
        if trades and r_arr.std() > 0 else None,
        "total_return_pct": round((equity / p["initial_equity"] - 1) * 100, 2),
        "final_equity": round(equity, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_bars_held": round(sum(t["bars_held"] for t in trades) / len(trades), 1)
        if trades else None,
        "period": {
            "from": candles[WARMUP]["time"] if n > WARMUP else None,
            "to": candles[-1]["time"],
            "bars": n,
        },
    }
    return {"metrics": metrics, "trades": trades, "equity_curve": curve, "params": p}


def _walk_forward(candles: list[dict], instrument: str, params: dict,
                  folds: int) -> dict[str, Any]:
    n = len(candles)
    folds = max(2, min(folds, 6))
    seg = (n - WARMUP) // (folds + 1)
    if seg < 150:
        return {"error": "недостаточно данных для walk-forward (нужно больше баров)"}
    details = []
    oos_trades = 0
    oos_pnl = 0.0
    for f in range(folds):
        train = candles[: WARMUP + seg * (f + 1)]
        test = candles[max(0, WARMUP + seg * (f + 1) - WARMUP - 20):
                       WARMUP + seg * (f + 2)]
        best_score, best_pf = params.get("min_score", 0.3), -1.0
        for ms in MIN_SCORE_GRID:
            r = simulate(train, instrument, {**params, "min_score": ms})
            pf = r["metrics"]["profit_factor"]
            if r["metrics"]["trades"] >= 5 and pf is not None and pf > best_pf:
                best_pf, best_score = pf, ms
        t = simulate(test, instrument, {**params, "min_score": best_score})
        details.append({
            "fold": f + 1, "optimized_min_score": best_score,
            "train_pf": round(best_pf, 2) if best_pf > 0 else None,
            "test": {k: t["metrics"][k] for k in
                     ("trades", "win_rate", "profit_factor", "total_return_pct",
                      "max_drawdown_pct")},
        })
        oos_trades += t["metrics"]["trades"]
        oos_pnl += t["metrics"]["final_equity"] - t["params"]["initial_equity"]
    return {"folds": details, "oos_trades": oos_trades,
            "oos_pnl_eur": round(oos_pnl, 2)}


async def run_backtest(db: Session, instrument: str, timeframe: str,
                       params: dict[str, Any], walk_forward_folds: int = 0) -> dict[str, Any]:
    creds = get_credentials(db)
    bars = int(params.get("bars", DEFAULT_PARAMS["bars"]))
    bars = max(300, min(bars, 5000))
    t0 = time.time()
    candles = await get_candles(creds, instrument, timeframe, bars + 1)
    candles = [c for c in candles if c["complete"]]  # forming bar would repaint
    if len(candles) < 300:
        raise ValueError(f"получено только {len(candles)} свечей — мало для бэктеста")

    result = simulate(candles, instrument, {**params, "bars": bars})
    wf = {}
    if walk_forward_folds:
        wf = _walk_forward(candles, instrument, result["params"], walk_forward_folds)

    row = BacktestRun(
        instrument=instrument, timeframe=timeframe,
        params=result["params"], metrics=result["metrics"],
        equity_curve=result["equity_curve"][-1000:],
        trades=result["trades"][-500:],
        walk_forward=wf,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "run_id": row.id,
        "instrument": instrument, "timeframe": timeframe,
        "metrics": result["metrics"], "trades": result["trades"][-200:],
        "equity_curve": result["equity_curve"],
        "walk_forward": wf,
        "elapsed_sec": round(time.time() - t0, 2),
    }


def run_to_dict(r: BacktestRun, with_detail: bool = False) -> dict[str, Any]:
    out = {
        "run_id": r.id, "instrument": r.instrument, "timeframe": r.timeframe,
        "params": r.params, "metrics": r.metrics,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "ai_analysis": r.ai_analysis,
    }
    if with_detail:
        out["trades"] = r.trades
        out["equity_curve"] = r.equity_curve
        out["walk_forward"] = r.walk_forward
    return out


def list_runs(db: Session, limit: int = 25) -> list[dict[str, Any]]:
    rows = db.scalars(select(BacktestRun)
                      .order_by(BacktestRun.created_at.desc()).limit(limit)).all()
    return [run_to_dict(r) for r in rows]


async def analyze_run(db: Session, anthropic_key: str, run_id: int) -> dict[str, Any]:
    """Sonnet critiques a stored run: weaknesses, characteristics, next steps."""
    from anthropic import AsyncAnthropic

    from ..services import memory

    row = db.get(BacktestRun, run_id)
    if row is None:
        raise ValueError("бэктест не найден")

    losers = sorted((t for t in (row.trades or [])), key=lambda t: t["pnl_eur"])[:8]
    losers_txt = "\n".join(
        f"- {t['direction']} score {t['score']}, {t['status']}, {t['pnl_eur']}€, "
        f"держали {t['bars_held']} баров" for t in losers)
    wf_txt = str(row.walk_forward) if row.walk_forward else "не проводился"

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1400,
            system=("Ты — квант-аналитик. Разбери результаты бэктеста: сильные и "
                    "слабые стороны, устойчивость (walk-forward), переоптимизация, "
                    "что улучшить ПЕРЕД живой торговлей. Конкретно, по-русски. "
                    "Помни: бэктест не учитывает ИИ-факторы и проскальзывание "
                    "смоделировано константой."),
            messages=[{"role": "user", "content":
                       f"Инструмент {row.instrument} {row.timeframe}\n"
                       f"Параметры: {row.params}\nМетрики: {row.metrics}\n"
                       f"Walk-forward: {wf_txt}\nХудшие сделки:\n{losers_txt or '—'}"}],
        )
        log_usage(SONNET_MODEL, "backtest_analysis",
                  resp.usage.input_tokens, resp.usage.output_tokens)
        text = "".join(b.text for b in resp.content if b.type == "text")
    finally:
        await client.close()

    row.ai_analysis = text
    db.commit()
    memory.add_memory(db, "lesson", f"Бэктест {row.instrument} {row.timeframe}",
                      text[:800], instrument=row.instrument,
                      timeframe=row.timeframe, importance=0.55, tags=["backtest"])
    return {"run_id": run_id, "analysis": text}
