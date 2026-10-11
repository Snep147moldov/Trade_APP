"""Бэктест того же детерминированного движка на исторических свечах.

Honesty rules:
  - AI defaults to zero; optional replay uses only point-in-time archived
    vectors. HTF, portfolio gates and adaptive memory are not simulated;
  - entries pay spread + slippage, every trade pays a flat commission (EUR);
  - inside a candle the stop is checked before the take-profit;
  - known opening gaps precede ambiguous high/low checks; stops fill at the
    worse open, targets conservatively at the limit without price improvement;
  - sizing compounds on current equity in a single-instrument account.

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
from ..performance import trade_metrics
from ..services import candles as candles_svc
from ..services.candles import get_candles, pip_size
from ..services.runtime import get_credentials, log_usage
from ..signals.engine import (ER_PERIOD, INVERTED_SIGNS, MEASURED_SIGNS,
                              TSMOM_LOOKBACK, score_components)
from ..i18n import t

WARMUP = 200
EXPIRY_BARS = 96
MIN_SCORE_GRID = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]

DEFAULT_PARAMS = {
    "ai_weight": 0.0,
    "strategy_variant": "confluence",
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
    "blocked_hours_utc": (),
    "max_cost_ratio": 0.0,  # 0 disables; spread + two adverse slippages / SL
    "trailing_enabled": False,
    "trailing_atr_mult": 1.5,
    "partial_tp_enabled": False,
    "partial_tp_at_r": 1.0,
    "partial_tp_fraction": 0.5,
    # перенос стопа в безубыток при +N R и сколько прибыли он запирает (в R).
    # 0/0 = выключено — так считались все прежние прогоны, и цифры из CLAUDE.md
    # остаются сравнимыми. Включать флагами --be / --be-lock.
    "breakeven_at_r": 0.0,
    "breakeven_lock_r": 0.0,
    # выход по времени ТОЛЬКО в плюсе (0 = выкл), в отличие от expiry_bars
    "profit_exit_bars": 0.0,
    "profit_exit_min_r": 0.3,
    # выход по времени: сколько баров держим сделку, если ни стоп, ни тейк не
    # сработали. Убыточные сделки достигают пика прибыли около 6-го бара, а
    # держатся ещё вдвое дольше — время выхода имеет значение само по себе.
    "expiry_bars": EXPIRY_BARS,
    # закрывать позиции перед пятничным закрытием рынка вместо переноса через
    # выходные. Спор: гэп в понедельник может выйти хуже -1R, но принудительный
    # выход отказывается от неотыгранной части ожидания. Проверяется замером.
    "weekend_flat": False,
    # торговать ПРОТИВ совокупной оценки (см. проверку знака ниже)
    "invert_signal": False,
    # часы UTC, в которые знаки НЕ инвертируются. Гипотеза: утро Лондона
    # (7-11 UTC) — единственное время, когда рынок действительно формирует
    # тренд, и там должна работать исходная трендовая формула, а не возврат
    # к среднему. Пусто = один режим на все сутки.
    "trend_hours_utc": (),
    # оставить в формуле только эти факторы (пусто = все)
    "factor_subset": (),
    # "original" — знаки как были; "measured" — исправленные по замеренному
    # information coefficient (см. signals.engine.MEASURED_SIGNS)
    "factor_signs": "original",
}


def _hour_utc(ts: float) -> int:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).hour


def _before_weekend(ts: float) -> bool:
    """Последний час перед пятничным закрытием рынка (21:00 UTC)."""
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.weekday() == 4 and dt.hour >= 20


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
    for i in range(100, n):
        if i >= 100:
            hurst[i] = ind.hurst_exponent(close[:i + 1], window=100)

    er = np.zeros(n)
    er_sign = np.ones(n)
    for i in range(ER_PERIOD, n):
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


def _validate(candles: list[dict], p: dict) -> None:
    import math

    if len(candles) <= WARMUP:
        raise ValueError(t("нужно больше {0} завершённых свечей", f"{WARMUP}"))
    previous = -float("inf")
    for c in candles:
        if not c.get("complete", False):
            raise ValueError(t("незавершённые свечи запрещены в бэктесте"))
        if not all(math.isfinite(c[k]) for k in ("time", "open", "high", "low", "close")):
            raise ValueError(t("нечисловые или бесконечные OHLC"))
        if (c["time"] <= previous or c["low"] <= 0
                or c["low"] > min(c["open"], c["close"])
                or c["high"] < max(c["open"], c["close"])):
            raise ValueError(t("повторные/неупорядоченные свечи или неверные OHLC"))
        previous = c["time"]
        quote_keys = [f"{side}_{k}" for side in ("bid", "ask") for k in ("open", "high", "low", "close")]
        if any(k in c for k in quote_keys):
            if not all(k in c and math.isfinite(c[k]) and c[k] > 0 for k in quote_keys):
                raise ValueError(t("неполные/неверные исторические bid/ask"))
            for side in ("bid", "ask"):
                if (c[f"{side}_low"] > min(c[f"{side}_open"], c[f"{side}_close"])
                        or c[f"{side}_high"] < max(c[f"{side}_open"], c[f"{side}_close"])):
                    raise ValueError(t("неверные исторические bid/ask OHLC"))
            if any(c[f"ask_{k}"] < c[f"bid_{k}"] for k in ("open", "close")):
                raise ValueError(t("отрицательный исторический спред"))
    for k in ("initial_equity", "risk_per_trade_pct", "risk_reward", "sl_atr_multiple",
              "expiry_bars", "trailing_atr_mult"):
        if not math.isfinite(p[k]) or p[k] <= 0:
            raise ValueError(t("{0} должен быть конечным и положительным", f"{k}"))
    for k in ("spread_pips", "slippage_pips", "commission_eur", "cooldown_bars",
              "breakeven_at_r", "breakeven_lock_r", "profit_exit_bars", "max_cost_ratio"):
        if not math.isfinite(p[k]) or p[k] < 0:
            raise ValueError(t("{0} не может быть отрицательным/нечисловым", f"{k}"))
    if not 0 < p["min_score"] <= 1 or not 0 < p["risk_per_trade_pct"] <= 100:
        raise ValueError(t("проверьте порог оценки и процент риска"))
    if not 0 < p["partial_tp_fraction"] < 1 or p["partial_tp_at_r"] <= 0:
        raise ValueError(t("неверные параметры частичной фиксации"))
    for k in ("expiry_bars", "cooldown_bars", "profit_exit_bars"):
        if int(p[k]) != p[k]:
            raise ValueError(t("{0} должен быть целым", f"{k}"))
    for k in ("partial_tp_at_r", "profit_exit_min_r", "min_adx"):
        if not math.isfinite(p[k]) or p[k] < 0:
            raise ValueError(t("{0} должен быть конечным и неотрицательным", f"{k}"))
    if p.get("invert_signal") and p.get("factor_signs") != "original":
        raise ValueError(t("invert_signal и factor_signs нельзя инвертировать одновременно"))
    for k in ("blocked_hours_utc", "trend_hours_utc"):
        if any(int(h) != h or not 0 <= h < 24 for h in p.get(k, ())):
            raise ValueError(t("{0}: часы должны быть целыми от 0 до 23", f"{k}"))


def simulate(candles: list[dict], instrument: str,
             params: dict[str, Any], *, start_index: int | None = None,
             precomputed: dict[str, np.ndarray] | None = None,
             entry_filter=None, historical_ai=None) -> dict[str, Any]:
    """Single-instrument research simulation on midpoint OHLC.

    Decide using bar i-1; enter at bar i open. Half the full bid/ask spread
    is paid at each side, with adverse slippage on both executions. Stops and
    targets are based on the executable entry, checked against exit-side quotes.
    `start_index` reserves earlier bars exclusively for indicator warm-up.
    """
    p = {**DEFAULT_PARAMS, **params}
    if not 0 <= p["ai_weight"] <= .5:
        raise ValueError(t("ai_weight должен быть от 0 до 0.5"))
    if p["ai_weight"] and historical_ai is None:
        raise ValueError(t("для AI-бэктеста нужны сохранённые исторические векторы"))
    _validate(candles, p)
    pre = precomputed if precomputed is not None else _precompute(candles)
    n = len(candles)
    start = max(WARMUP, start_index if start_index is not None else WARMUP)
    if start >= n:
        raise ValueError(t("нет свечей в периоде оценки"))
    half_spread = p["spread_pips"] * pip_size(instrument) / 2
    slip = p["slippage_pips"] * pip_size(instrument)
    equity = float(p["initial_equity"])
    peak = equity
    max_dd = 0.0
    realized_peak = equity
    realized_dd = 0.0
    curve = [{"time": candles[start]["time"], "value": equity}]
    trades: list[dict] = []
    pos = None
    last_entry = -10_000
    rejected_cost = 0
    ai_bars = 0

    for i in range(start, n):
        c = candles[i]
        # Order decision knows neither this bar's high/low nor its close.
        if pos is None and equity > 0 and i - last_entry >= p["cooldown_bars"]:
            snap = _snap(pre, i - 1)
            hour = _hour_utc(c["time"])
            trend_hour = hour in (p.get("trend_hours_utc") or ())
            signs = None if trend_hour else {
                "measured": MEASURED_SIGNS, "inverted": INVERTED_SIGNS
            }.get(p.get("factor_signs"))
            news, prediction, available = historical_ai.at(c["time"], instrument) if historical_ai is not None else (0., 0., False)
            ai_bars += int(available)
            _, _, score, regime = score_components(
                snap, news, prediction, p["min_adx"], ai_weight=p["ai_weight"],
                factor_signs=signs, factor_subset=tuple(p.get("factor_subset") or ()) or None,
                strategy_variant=p["strategy_variant"])
            if p.get("invert_signal") and not trend_hour:
                score = -score
            dist = p["sl_atr_multiple"] * (snap["atr14"] or 0)
            observed_spread = (c["ask_open"] - c["bid_open"]
                               if "ask_open" in c and "bid_open" in c else 2 * half_spread)
            cost_ratio = (observed_spread + 2 * slip) / dist if dist > 0 else float("inf")
            cost_ok = not p["max_cost_ratio"] or cost_ratio <= p["max_cost_ratio"]
            eligible = (abs(score) >= p["min_score"] and dist > 0
                        and hour not in (p.get("blocked_hours_utc") or ())
                        and not (p["weekend_flat"] and _before_weekend(c["time"])))
            if eligible and not cost_ok:
                rejected_cost += 1
            features = None
            if eligible and cost_ok:
                from .probability import entry_features
                features = entry_features(snap, score, cost_ratio)
                if entry_filter is not None and not entry_filter(features):
                    eligible = False
            risk = equity * p["risk_per_trade_pct"] / 100
            if eligible and cost_ok and risk > p["commission_eur"]:
                side = 1.0 if score > 0 else -1.0
                entry_quote = c.get("ask_open" if side > 0 else "bid_open",
                                    c["open"] + side * half_spread)
                entry = entry_quote + side * slip
                # The stop risk budget includes expected stop slippage and fees.
                value_per_price = (risk - p["commission_eur"]) / (dist + slip)
                pos = {"bar": i, "side": side, "entry": entry,
                       "sl": entry - side * dist, "initial_sl": entry - side * dist,
                       "tp": entry + side * dist * p["risk_reward"],
                       "risk_dist": dist, "risk_eur": risk, "value_per_price": value_per_price,
                       "score": score, "regime": regime, "be": False,
                       "features": features,
                       "partial": 0.0, "partial_pnl": 0.0}
                last_entry = i

        if pos:
            side = pos["side"]
            buy = side > 0
            # Constant-spread approximation to bid (long exit) / ask (short).
            quote_side = "bid" if buy else "ask"
            op, hi, lo, cl = (c.get(f"{quote_side}_{k}", c[k] - side * half_spread)
                              for k in ("open", "high", "low", "close"))
            stop = lo <= pos["sl"] if buy else hi >= pos["sl"]
            target = hi >= pos["tp"] if buy else lo <= pos["tp"]
            gap_sl = op <= pos["sl"] if buy else op >= pos["sl"]
            gap_tp = op >= pos["tp"] if buy else op <= pos["tp"]
            px, status = None, None
            # The open is observed first. Only the remaining intrabar path is
            # ambiguous; a known TP gap cannot subsequently become an SL hit.
            if gap_sl:
                px, status = op, "hit_sl"
            elif gap_tp:
                px, status = pos["tp"], "hit_tp"  # conservative limit fill
            elif stop:
                px, status = pos["sl"], "hit_sl"
            elif target:
                px, status = pos["tp"], "hit_tp"
            held = i - pos["bar"] + 1
            close_r = side * (cl - pos["entry"]) / pos["risk_dist"]
            if px is None:
                if p["profit_exit_bars"] > 0 and held >= p["profit_exit_bars"] and close_r >= p["profit_exit_min_r"]:
                    px, status = cl, "profit_exit"
                elif held >= p["expiry_bars"]:
                    px, status = cl, "expired"
                elif p["weekend_flat"] and _before_weekend(c["time"]):
                    px, status = cl, "weekend_flat"
                elif i == n - 1:
                    px, status = cl, "end_of_data"
            best_r = side * ((hi if buy else lo) - pos["entry"]) / pos["risk_dist"]
            if (p["partial_tp_enabled"] and not pos["partial"] and status != "hit_sl"
                    and best_r >= p["partial_tp_at_r"] < p["risk_reward"]):
                pos["partial"] = p["partial_tp_fraction"]
                partial_px = pos["entry"] + side * pos["risk_dist"] * p["partial_tp_at_r"] - side * slip
                pos["partial_pnl"] = pos["partial"] * side * (partial_px - pos["entry"]) * pos["value_per_price"]
            if px is not None:
                exit_price = px - side * slip
                pnl = (pos["partial_pnl"] + (1 - pos["partial"]) * side
                       * (exit_price - pos["entry"]) * pos["value_per_price"] - p["commission_eur"])
                equity += pnl
                realized_peak = max(realized_peak, equity)
                realized_dd = max(realized_dd, 100 * (realized_peak - equity) / realized_peak)
                trades.append({
                    "signal_time": candles[pos["bar"] - 1]["time"],
                    "entry_time": candles[pos["bar"]]["time"], "exit_time": c["time"],
                    "direction": "BUY" if buy else "SELL", "entry": pos["entry"],
                    "exit": exit_price, "sl": pos["sl"], "initial_sl": pos["initial_sl"],
                    "tp": pos["tp"], "risk_dist": pos["risk_dist"], "risk_eur": pos["risk_eur"],
                    "bars_held": held, "r": pnl / pos["risk_eur"],
                    "gross_r": side * (exit_price - pos["entry"]) / pos["risk_dist"],
                    "pnl_eur": pnl, "status": status, "score": pos["score"],
                    "regime": pos["regime"], "equity_after": equity,
                    "features": pos["features"],
                })
                pos = None
            else:
                # Improvements become executable next bar; do not place a stop
                # on the wrong side of the current executable market price.
                if p["breakeven_at_r"] > 0 and not pos["be"] and best_r >= p["breakeven_at_r"] and close_r > 0:
                    lock = min(p["breakeven_lock_r"], close_r)
                    candidate = pos["entry"] + side * lock * pos["risk_dist"]
                    pos["sl"] = max(pos["sl"], candidate) if buy else min(pos["sl"], candidate)
                    pos["be"] = True
                if p["trailing_enabled"]:
                    trail = (hi if buy else lo) - side * p["trailing_atr_mult"] * pre["atr14"][i]
                    trail = min(trail, cl) if buy else max(trail, cl)
                    pos["sl"] = max(pos["sl"], trail) if buy else min(pos["sl"], trail)
        marked = equity
        if pos:
            marked += (pos["partial_pnl"] + (1 - pos["partial"]) * pos["side"]
                       * (cl - pos["side"] * slip - pos["entry"])
                       * pos["value_per_price"] - p["commission_eur"])
        peak = max(peak, marked)
        max_dd = max(max_dd, 100 * (peak - marked) / peak)
        point = {"time": c["time"], "value": round(marked, 2)}
        if curve[-1]["time"] == c["time"]:
            curve[-1] = point
        else:
            curve.append(point)

    metrics = {**trade_metrics(trades),
        "total_return_pct": round((equity / p["initial_equity"] - 1) * 100, 4),
        "final_equity": round(equity, 2), "max_drawdown_pct": round(max_dd, 4),
        "realized_max_drawdown_pct": round(realized_dd, 4),
        "avg_bars_held": sum(t["bars_held"] for t in trades) / len(trades) if trades else None,
        "period": {"from": candles[start]["time"], "to": candles[-1]["time"], "bars": n - start},
        "cost_rejections": rejected_cost, "forced_closes": sum(t["status"] == "end_of_data" for t in trades),
        "ai_evaluated_bars": ai_bars,
        "data_source": "simulation" if candles_svc.is_simulated(candles) else "market",
        "execution_model": "next_open_bid_ask_v2" if "bid_open" in candles[0]
                           else "next_open_midpoint_half_spread_each_side_v2",
        "drawdown_basis": "bar_close_mark_to_market", "confidence_kind": "heuristic_uncalibrated",
        "scope": "single_instrument_no_memory_htf_or_portfolio_limits",
    }
    return {"metrics": metrics, "trades": trades, "equity_curve": curve, "params": p}


def _walk_forward(candles: list[dict], instrument: str, params: dict,
                  folds: int, historical_ai=None) -> dict[str, Any]:
    n = len(candles)
    folds = max(2, min(folds, 6))
    seg = (n - WARMUP) // (folds + 1)
    if seg < 150:
        return {"error": t("недостаточно данных для walk-forward (нужно больше баров)")}
    pre = _precompute(candles)
    details = []
    all_trades = []
    initial = params.get("initial_equity", DEFAULT_PARAMS["initial_equity"])
    equity = initial
    for f in range(folds):
        boundary = WARMUP + seg * (f + 1)
        end = n if f == folds - 1 else WARMUP + seg * (f + 2)
        best_score, best_quality, best_metrics = params.get("min_score", 0.3), -float("inf"), None
        for ms in MIN_SCORE_GRID:
            r = simulate(candles[:boundary], instrument,
                         {**params, "min_score": ms}, precomputed=pre, historical_ai=historical_ai)
            rs = np.array([t["r"] for t in r["trades"]])
            if len(rs) < 20:
                continue
            # A lower confidence bound penalizes tiny, volatile lucky samples.
            quality = float(rs.mean() - 1.96 * rs.std(ddof=1) / np.sqrt(len(rs)))
            if quality > best_quality:
                best_quality, best_score, best_metrics = quality, ms, r["metrics"]
        if equity <= 0:
            break
        # All earlier observations are indicator-only. No entry, outcome or
        # equity from training can be counted as an out-of-sample observation.
        t = simulate(candles[:end], instrument,
                     {**params, "min_score": best_score, "initial_equity": equity},
                     start_index=boundary, precomputed=pre, historical_ai=historical_ai)
        equity = t["metrics"]["final_equity"]
        details.append({
            "fold": f + 1, "optimized_min_score": best_score,
            "train_pf": best_metrics["profit_factor"] if best_metrics else None,
            "selection": "train_net_r_lower_bound" if best_metrics else "insufficient_training_trades_default",
            "train_to": candles[boundary - 1]["time"],
            "test_from": candles[boundary]["time"], "test_to": candles[end - 1]["time"],
            "test": t["metrics"],
        })
        all_trades.extend(t["trades"])
    return {"folds": details, "oos_trades": len(all_trades),
            "oos_pnl_eur": round(equity - initial, 2),
            "oos_metrics": trade_metrics(all_trades),
            "boundary_policy": "flat_at_each_boundary; past_bars_only_for_indicators"}


async def run_backtest(db: Session, instrument: str, timeframe: str,
                       params: dict[str, Any], walk_forward_folds: int = 0) -> dict[str, Any]:
    creds = get_credentials(db)
    bars = int(params.get("bars", DEFAULT_PARAMS["bars"]))
    bars = max(300, min(bars, 5000))
    t0 = time.time()
    candles = await get_candles(creds, instrument, timeframe, bars + 1)
    candles = [c for c in candles if c["complete"]]  # forming bar would repaint
    if len(candles) < 300:
        raise ValueError(t("получено только {0} свечей — мало для бэктеста", f"{len(candles)}"))

    # Провайдер мог молча отдать синтетику (нет ключа / инструмент не отдался).
    # Это гладкая сумма синусов: трендовая стратегия показывает на ней WR 65–85%
    # и PF>3, которых на реальном рынке нет. Результат обязан быть помечен,
    # иначе такие цифры принимают за рабочую стратегию.
    simulated = candles_svc.is_simulated(candles)
    issues = candles_svc.market_data_issues(candles, instrument, timeframe)
    if issues:
        raise ValueError(t("неподтверждённые данные: ") + "; ".join(issues))
    if simulated:
        raise ValueError(t("провайдер вернул синтетические свечи — оценка стратегии запрещена"))

    history = None
    if params.get("ai_weight", 0):
        from .ai_history import AIHistory
        from ..models import NewsAnalysis
        rows = db.scalars(select(NewsAnalysis).order_by(NewsAnalysis.created_at)).all()
        if not rows:
            raise ValueError(t("нет сохранённых исторических AI-векторов"))
        history = AIHistory([{"created_at": r.created_at, "vector": r.vector,
                              "pair_biases": r.pair_biases} for r in rows])
    result = simulate(candles, instrument, {**params, "bars": bars}, historical_ai=history)
    result["metrics"]["data_source"] = "simulation" if simulated else "market"
    if simulated:
        result["metrics"]["warning"] = (
            t("СИНТЕТИЧЕСКИЕ ДАННЫЕ: провайдер не отдал реальные свечи, использован встроенный симулятор. Эти метрики НЕ отражают рынок и не годятся для оценки стратегии — проверьте ключи API."))
    wf = {}
    if walk_forward_folds:
        wf = _walk_forward(candles, instrument, result["params"], walk_forward_folds, historical_ai=history)

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
    metrics = dict(r.metrics or {})
    if "data_source" not in metrics:
        metrics.update(data_source="unknown", warning=t("Источник старого прогона не подтверждён; не используйте его для оценки стратегии"))
    out = {
        "run_id": r.id, "instrument": r.instrument, "timeframe": r.timeframe,
        "params": r.params, "metrics": metrics,
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
        raise ValueError(t("бэктест не найден"))

    losers = sorted((t for t in (row.trades or [])), key=lambda t: t["pnl_eur"])[:8]
    losers_txt = "\n".join(
        t("- {0} score {1}, {2}, {3}€, держали {4} баров", f"{t['direction']}", f"{t['score']}", f"{t['status']}", f"{t['pnl_eur']}", f"{t['bars_held']}") for t in losers)
    wf_txt = str(row.walk_forward) if row.walk_forward else t("не проводился")

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1400,
            system=(t("Ты — квант-аналитик. Разбери результаты бэктеста: сильные и слабые стороны, устойчивость (walk-forward), переоптимизация, что улучшить ПЕРЕД живой торговлей. Конкретно, по-русски. Помни: бэктест не учитывает ИИ-факторы и проскальзывание смоделировано константой.")),
            messages=[{"role": "user", "content":
                       t("Инструмент {0} {1}\nПараметры: {2}\nМетрики: {3}\nWalk-forward: {4}\nХудшие сделки:\n{5}", f"{row.instrument}", f"{row.timeframe}", f"{row.params}", f"{row.metrics}", f"{wf_txt}", f"{losers_txt or '—'}")}],
        )
        log_usage(SONNET_MODEL, "backtest_analysis",
                  resp.usage.input_tokens, resp.usage.output_tokens)
        text = "".join(b.text for b in resp.content if b.type == "text")
    finally:
        await client.close()

    row.ai_analysis = text
    db.commit()
    memory.add_memory(db, "lesson", t("Бэктест {0} {1}", f"{row.instrument}", f"{row.timeframe}"),
                      text[:800], instrument=row.instrument,
                      timeframe=row.timeframe, importance=0.55, tags=["backtest"])
    return {"run_id": run_id, "analysis": text}
