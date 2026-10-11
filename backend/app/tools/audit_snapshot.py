"""Recalculate stored broker results without blending them with paper trades."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ..performance import trade_metrics


def report(snapshot):
    all_closed = [s for s in snapshot['signals'] if s['status'] in ('hit_tp','hit_sl','expired')]
    broker = [s for s in all_closed if (s.get('mt5_orders') or 0) > 0 and s.get('mt5_pnl') is not None]

    def metrics(rows):
        trades = []
        for s in rows:
            money = s.get('mt5_pnl') if (s.get('mt5_orders') or 0) > 0 else s.get('pnl_money')
            if money is None or not s.get('risk_amount') or s['risk_amount'] <= 0:
                continue
            trades.append({'pnl_eur':money, 'r':money/s['risk_amount']})
        m = trade_metrics(trades)
        m['pnl_eur'] = round(sum(t['pnl_eur'] for t in trades), 2)
        m['mean_win_r'] = sum(t['r'] for t in trades if t['r'] > 0)/m['wins'] if m['wins'] else None
        m['mean_loss_r'] = -sum(t['r'] for t in trades if t['r'] < 0)/m['losses'] if m['losses'] else None
        return m

    def groups(rows, key):
        groups = defaultdict(list)
        for s in rows:
            groups[key(s)].append(s)
        return {k:metrics(v) for k,v in groups.items()}

    def asset(s):
        sym=s['instrument']
        return 'metals' if sym.startswith(('XAU','XAG','XPT')) else ('majors' if 'USD' in sym else 'crosses')

    recent=[s for s in broker if s['created_at'][:10] >= '2026-08-28']
    legacy_wins=sum((s.get('pnl_money') or 0)>0 for s in all_closed)
    legacy={'trades':len(all_closed), 'wins':legacy_wins,
            'losses_including_zero':len(all_closed)-legacy_wins,
            'win_rate':round(100*legacy_wins/len(all_closed),2) if all_closed else None,
            'pnl_eur':round(sum(s.get('pnl_money') or 0 for s in all_closed),2),
            'definition':'original journal/dashboard: all closed Signal.pnl_money, zeros as losses'}
    confidence = {}
    for lo,hi in ((0,.6),(.6,.7),(.7,.8),(.8,1.01)):
        confidence[f'{lo:.1f}-{min(hi,1):.1f}'] = metrics([s for s in broker if lo <= s['confidence'] < hi])
    return {'source':'stored VPS Signal.mt5_pnl; full raw broker reconciliation unavailable',
            'total_signals':len(snapshot['signals']), 'all_closed':len(all_closed),
            'legacy_dashboard':legacy, 'broker':metrics(broker),
            'by_timeframe':groups(broker, lambda s:s['timeframe']),
            'by_asset_group':groups(broker,asset), 'by_confidence_strength':confidence,
            'recent_from':'2026-08-28 by entry date', 'recent_broker':metrics(recent),
            'recent_by_asset':groups(recent,asset),
            'archived_ai_rows':len(snapshot['news']), 'strategy':snapshot['strategy']}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    raw=a.snapshot.read_bytes()
    r=report(json.loads(raw));r['snapshot_sha256']=hashlib.sha256(raw).hexdigest()
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False))
    print(json.dumps({k:r[k] for k in ('total_signals','all_closed','broker','recent_broker')},indent=2))
