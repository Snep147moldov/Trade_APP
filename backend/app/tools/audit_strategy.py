"""Reproducible train/validation/holdout comparison on saved market candles.

No broker orders, API calls, credentials or production settings are touched.
Selection uses only training outcomes. Validation checks the selected candidate
once; the holdout is evaluated after selection.json is written. Changing the
candidate grid after inspecting results consumes the holdout.
"""

import argparse
import hashlib
import json
import math
import time
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

import numpy as np

from ..backtest.engine import DEFAULT_PARAMS, WARMUP, _precompute, simulate
from ..performance import trade_metrics
from ..services.candles import market_data_issues


def uncertainty(trades: list[dict]) -> dict:
    """Week clusters keep same-period correlated FX trades together."""
    m = trade_metrics(trades)
    if not trades:
        return {**m, "expectancy_r_lcb95": None}
    clusters = defaultdict(list)
    for t in trades:
        clusters[int(t["entry_time"]) // (7 * 86400)].append(t["r"])
    avg = m["expectancy_r"]
    g = len(clusters)
    residuals = [sum(rs) - len(rs) * avg for rs in clusters.values()]
    se = math.sqrt(g / (g - 1) * sum(x*x for x in residuals)) / len(trades) if g > 1 else None
    return {**m, "week_clusters": g, "expectancy_r_lcb95": avg - 1.96 * se if se is not None else None,
            "expectancy_r_ucb95": avg + 1.96 * se if se is not None else None}


def candidate_grid(baseline: dict) -> list[dict]:
    # Freeze this small grid before observing results. No hour/pair search,
    # no TP shortening to inflate win rate, no risk increase.
    rows = []
    for signs in ("original", "inverted"):
        for threshold in (0.25, 0.35, 0.45):
            for stop in (1.5, 2.0):
                p = {**baseline, "factor_signs": signs, "min_score": threshold,
                     "sl_atr_multiple": stop, "trend_hours_utc": []}
                rows.append({"name": f"{signs}_score{threshold}_sl{stop}", "params": p})
    for threshold in (0.25, 0.35):
        rows.append({"name": f"regime_balanced_score{threshold}", "params": {
            **baseline, "factor_signs": "original", "strategy_variant": "regime_balanced",
            "trend_hours_utc": [], "min_score": threshold}})
    return rows


def main(data_dir: Path, output: Path, snapshot: Path | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    data = {}
    fingerprints = {}
    for path in sorted(data_dir.glob('*.json')):
        if path.name == "manifest.json":
            continue
        candles = json.loads(path.read_text())
        if not isinstance(candles, list) or not candles:
            continue
        sym = path.stem
        issues = market_data_issues(candles, sym, "1h")
        if issues:
            raise ValueError(f"{sym}: {'; '.join(issues)}")
        data[sym] = candles
        fingerprints[sym] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not data:
        raise ValueError("no market candle files")
    shared = sorted(set.intersection(*({c["time"] for c in cs} for cs in data.values())))
    usable = shared[WARMUP:]
    train_end = usable[int(len(usable) * 0.60)]
    validation_end = usable[int(len(usable) * 0.80)]
    baseline = {**DEFAULT_PARAMS, "factor_signs": "inverted", "min_score": 0.25,
                "risk_reward": 1.8, "sl_atr_multiple": 2.0, "trend_hours_utc": [9, 10, 11],
                "risk_per_trade_pct": 1.0, "max_cost_ratio": 0.25}
    if snapshot:
        settings = json.loads(snapshot.read_text())["strategy"]
        baseline.update({k: v for k, v in settings.items() if k in baseline})
        # Isolate selection quality from leverage, portfolio sizing and account
        # changes. All variants use the same research risk and per-pair capital.
        baseline.update(risk_per_trade_pct=1.0, initial_equity=10000.0)
    candidates = candidate_grid(baseline)
    protocol = {"split": "shared-calendar 60/20/20; flat boundaries; past warmup only",
                "train_to_exclusive": train_end, "validation_to_exclusive": validation_end,
                "holdout_to": usable[-1], "data_sha256": fingerprints,
                "baseline": baseline, "candidates": candidates,
                "costs": "historical bid/ask; 0.2 pip slippage per side; no historical swap/commission",
                "selection": "maximize train win rate among positive weekly R lower bounds; otherwise best R lower bound (research only)",
                "deployment": "none", "created_at_epoch": time.time()}
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2))
    pre = {}
    for sym, cs in data.items():
        pre[sym] = _precompute(cs)
        print("indicators", sym, len(cs), flush=True)

    def run(p, segment):
        trades = []
        by_symbol = {}
        for sym, cs in data.items():
            ts = [c["time"] for c in cs]
            lo, hi = {"train": (shared[WARMUP], train_end),
                      "validation": (train_end, validation_end),
                      "holdout": (validation_end, usable[-1] + 1),
                      "full": (shared[WARMUP], usable[-1] + 1)}[segment]
            start, end = bisect_left(ts, lo), bisect_left(ts, hi)
            r = simulate(cs[:end], sym, p, start_index=start, precomputed=pre[sym])
            for t in r["trades"]:
                t["instrument"] = sym
            trades.extend(r["trades"])
            by_symbol[sym] = r["metrics"]
        return {"metrics": uncertainty(trades), "by_symbol": by_symbol, "trades": trades}

    train_baseline = run(baseline, "train")
    scored = []
    for candidate in candidates:
        r = run(candidate["params"], "train")
        scored.append({**candidate, "train": r["metrics"]})
        print("train", candidate["name"], r["metrics"]["win_rate"], r["metrics"]["expectancy_r"], flush=True)
    eligible = [c for c in scored if c["train"]["trades"] >= 100
                and (c["train"]["expectancy_r_lcb95"] or -1) > 0]
    selected = max(eligible, key=lambda c: (c["train"]["win_rate"], c["train"]["expectancy_r"])) if eligible else \
        max(scored, key=lambda c: c["train"]["expectancy_r_lcb95"] if c["train"]["expectancy_r_lcb95"] is not None else -float("inf"))
    val_base = run(baseline, "validation")
    val_selected = run(selected["params"], "validation")
    vm, bm = val_selected["metrics"], val_base["metrics"]
    accepted = bool(eligible and vm["trades"] >= 50
                    and vm["win_rate"] > bm["win_rate"]
                    and vm["expectancy_r"] > max(0, bm["expectancy_r"]))
    selection = {"selected": selected, "training_grid": scored,
                 "validation_baseline": bm, "validation_selected": vm,
                 "validation_accepted": accepted}
    (output / "selection.json").write_text(json.dumps(selection, indent=2))
    # First and only evaluation of the holdout after freezing the candidate.
    held_base = run(baseline, "holdout")
    held_selected = run(selected["params"], "holdout")
    sensitivity = {}
    for slip in (0.0, 0.5, 1.0):
        sensitivity[str(slip)] = {
            "baseline": run({**baseline, "slippage_pips": slip}, "holdout")["metrics"],
            "selected": run({**selected["params"], "slippage_pips": slip}, "holdout")["metrics"]}
    def compact(r):
        return {k: v for k, v in r.items() if k != "trades"}
    result = {"protocol": protocol, "selection": selection,
              "train_baseline": compact(train_baseline),
              "validation_baseline": compact(val_base), "validation_selected": compact(val_selected),
              "holdout_baseline": compact(held_base), "holdout_selected": compact(held_selected),
              "full_baseline": compact(run(baseline, "full")),
              "slippage_sensitivity": sensitivity,
              "limitations": ["pooled independent accounts, not portfolio returns",
                              "no AI, memory, HTF or live execution/portfolio gates",
                              "no swap or broker-specific commissions/lot quantization",
                              "binomial WR interval ignores dependence; R uses week clusters",
                              "historic periods may overlap previous manual experiments"]}
    (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    (output / "holdout_trades.json").write_text(json.dumps({"baseline": held_base["trades"],
                                                           "selected": held_selected["trades"]}))
    print(json.dumps({"selected": selected["name"], "validation_accepted": accepted,
                      "baseline_holdout": held_base["metrics"], "selected_holdout": held_selected["metrics"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    main(args.data_dir, args.output, args.snapshot)
