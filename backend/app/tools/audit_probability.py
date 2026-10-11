"""Train/calibrate a probability filter and reserve September as final test."""

import argparse
import json
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..backtest.engine import DEFAULT_PARAMS, WARMUP, _precompute, simulate
from ..backtest.probability import calibrated_predict, fit, predict
from ..services.candles import market_data_issues
from .audit_strategy import uncertainty


def main(data_dir: Path, output: Path, snapshot: Path):
    output.mkdir(parents=True, exist_ok=True)
    data = {p.stem: json.loads(p.read_text()) for p in data_dir.glob('*.json')
            if p.name != 'manifest.json'}
    settings = json.loads(snapshot.read_text())["strategy"]
    params = {**DEFAULT_PARAMS, **{k: v for k, v in settings.items() if k in DEFAULT_PARAMS},
              "risk_per_trade_pct": 1.0, "initial_equity": 10000.0}
    dates = [int(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp())
             for t in ('2026-07-01', '2026-07-16', '2026-09-01')]
    pre = {}
    for sym, cs in data.items():
        issues = market_data_issues(cs, sym, "1h")
        if issues:
            raise ValueError(f"{sym}: {issues}")
        pre[sym] = _precompute(cs)
        print("indicators", sym, flush=True)

    def run(lo, hi, gate=None):
        trades = []
        for sym, cs in data.items():
            ts = [c["time"] for c in cs]
            start = max(WARMUP, bisect_left(ts, lo))
            end = bisect_left(ts, hi)
            if end <= start:
                continue
            out = simulate(cs[:end], sym, params, start_index=start,
                           precomputed=pre[sym], entry_filter=gate)
            trades.extend({**t, "instrument": sym} for t in out["trades"])
        return trades

    train = [t for t in run(0, dates[0]) if t["status"] != "end_of_data"]
    calibration = [t for t in run(dates[0], dates[1]) if t["status"] != "end_of_data"]
    model = fit([t["features"] for t in train], [int(t["pnl_eur"] > 0) for t in train])
    probs = np.clip(predict(model, [t["features"] for t in calibration]), 1e-6, 1 - 1e-6)
    calibrator = fit(np.log(probs / (1 - probs))[:, None],
                     [int(t["pnl_eur"] > 0) for t in calibration], l2=10)
    base_validation = run(dates[1], dates[2])
    base_stats = uncertainty(base_validation)
    variants = []
    breakeven = 1 / (1 + params["risk_reward"])
    for extra in (0.03, 0.05, 0.10):
        threshold = breakeven + extra
        gate = lambda features: calibrated_predict(model, calibrator, features)[0] >= threshold
        trades = run(dates[1], dates[2], gate)
        variants.append({"threshold": threshold, "validation": uncertainty(trades)})
    eligible = [v for v in variants if v["validation"]["trades"] >= 50
                and v["validation"]["expectancy_r"] > 0
                and v["validation"]["win_rate"] > base_stats["win_rate"]]
    # Never pick a threshold on September; even a failed model is frozen first.
    selected = max(eligible, key=lambda v: v["validation"]["expectancy_r"]) if eligible else variants[0]
    frozen = {"model": model, "calibration": calibrator, "threshold": selected["threshold"],
              "params": params, "train": uncertainty(train), "calibration_sample": uncertainty(calibration),
              "validation_baseline": base_stats, "validation_variants": variants,
              "validation_accepted": bool(eligible), "train_end": dates[0],
              "calibration_end": dates[1], "holdout_start": dates[2],
              "live_enabled": False}
    (output / 'probability_model.json').write_text(json.dumps(frozen, indent=2))
    end = min(cs[-1]["time"] for cs in data.values()) + 1
    base = run(dates[2], end)
    gate = lambda features: calibrated_predict(model, calibrator, features)[0] >= selected["threshold"]
    filtered = run(dates[2], end, gate)
    y = np.array([int(t["pnl_eur"] > 0) for t in base])
    probs = calibrated_predict(model, calibrator, [t["features"] for t in base]) if base else np.array([])
    constant = sum(t["pnl_eur"] > 0 for t in train) / len(train)
    reliability = []
    for lo, hi in ((0, .3), (.3, .4), (.4, .5), (.5, 1.01)):
        mask = (probs >= lo) & (probs < hi)
        if mask.any():
            reliability.append({"range": [lo, hi], "count": int(mask.sum()),
                                "mean_prediction": float(probs[mask].mean()),
                                "observed_win_rate": float(y[mask].mean())})
    result = {**frozen, "holdout_end": end - 1, "baseline": uncertainty(base),
              "filtered": uncertainty(filtered), "reliability": reliability,
              "brier_model": float(np.mean((probs - y)**2)) if len(y) else None,
              "brier_constant_training_rate": float(np.mean((constant - y)**2)) if len(y) else None,
              "scope": "research only; selection filter replayed, not retrospective deletion of trades",
              "limitations": ["short September test; weak regime coverage", "no historical LLM news replay",
                              "no portfolio gates/HTF; no promotion based on a small win-rate increase"]}
    (output / 'probability_results.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({k: result[k] for k in ("validation_accepted", "threshold", "baseline", "filtered",
                                            "brier_model", "brier_constant_training_rate")}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    main(args.data_dir, args.output, args.snapshot)
