"""Ablate recorded LLM news/bias vectors with point-in-time availability."""

import argparse
import json
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

from ..backtest.ai_history import AIHistory
from ..backtest.engine import DEFAULT_PARAMS, WARMUP, _precompute, simulate
from ..services.candles import market_data_issues
from .audit_strategy import uncertainty


def main(data_dir, output, snapshot):
    output.mkdir(parents=True, exist_ok=True)
    saved = json.loads(snapshot.read_text())
    history = AIHistory(saved['news'])
    data = {p.stem: json.loads(p.read_text()) for p in data_dir.glob('*.json') if p.name != 'manifest.json'}
    params = {**DEFAULT_PARAMS, **{k: v for k, v in saved['strategy'].items() if k in DEFAULT_PARAMS},
              'risk_per_trade_pct': 1., 'initial_equity': 10000.}
    pre = {}
    for sym, cs in data.items():
        issues = market_data_issues(cs, sym, '1h')
        if issues:
            raise ValueError(f'{sym}: {issues}')
        pre[sym] = _precompute(cs)
    start, boundary = [int(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp())
                       for t in ('2026-07-16', '2026-09-01')]
    end = min(cs[-1]['time'] for cs in data.values()) + 1

    def run(weight, lo, hi):
        trades = []
        for sym, cs in data.items():
            times = [c['time'] for c in cs]
            first, last = max(WARMUP, bisect_left(times, lo)), bisect_left(times, hi)
            if last <= first:
                continue
            r = simulate(cs[:last], sym, {**params, 'ai_weight': weight}, start_index=first,
                         precomputed=pre[sym], historical_ai=history)
            trades.extend(r['trades'])
        return uncertainty(trades)

    variants = [{'weight': w, 'validation': run(w, start, boundary)} for w in (0., .05, .10, .15)]
    selected = max(variants, key=lambda v: v['validation']['expectancy_r_lcb95'])
    frozen = {'selection_window': [start, boundary], 'holdout_window': [boundary, end-1],
              'variants': variants, 'selected_weight': selected['weight'],
              'validation_accepted': selected['validation']['expectancy_r_lcb95'] > 0,
              'archive_rows': len(saved['news']), 'availability': 'persisted_at <= decision time',
              'decay_half_life_hours': 12, 'live_enabled': False}
    (output / 'ai_selection.json').write_text(json.dumps(frozen, indent=2))
    result = {**frozen, 'baseline_holdout': run(0, boundary, end),
              'selected_holdout': run(selected['weight'], boundary, end),
              'limitations': ['historical provider-era effects', 'short September sample',
                              'no historical memory adaptation or HTF',
                              'vector replay does not recreate a new LLM model on old news']}
    (output / 'ai_results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--snapshot', type=Path, required=True)
    args = p.parse_args()
    main(args.data_dir, args.output, args.snapshot)
