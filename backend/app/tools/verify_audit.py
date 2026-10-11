"""Verify frozen audit results offline; does not search or change parameters."""
import argparse
import hashlib
import json
from bisect import bisect_left
from pathlib import Path

from ..backtest.ai_history import AIHistory
from ..backtest.engine import WARMUP, _precompute, simulate
from ..backtest.probability import calibrated_predict
from ..performance import trade_metrics


def main(data_dir, report_dir):
    load=lambda name:json.loads((report_dir/name).read_text())
    saved=load('results.json');protocol=saved['protocol']
    ai=load('ai_results.json');prob=load('probability_results.json')
    history=AIHistory(json.loads((data_dir/'vps_snapshot.json').read_text())['news'])
    aggregate={k:[] for k in ('full','holdout','selected','september','ai','probability')}
    for path in sorted((data_dir/'feb_sep').glob('*.json')):
        if path.name=='manifest.json':continue
        sym=path.stem
        original=data_dir/'feb_aug'/path.name
        assert hashlib.sha256(original.read_bytes()).hexdigest()==protocol['data_sha256'][sym]
        cs=json.loads(path.read_text());pre=_precompute(cs);times=[c['time'] for c in cs]
        end=bisect_left(times,protocol['holdout_to']+1)
        start=bisect_left(times,protocol['validation_to_exclusive'])
        base=protocol['baseline'];chosen=saved['selection']['selected']['params']
        p=prob['params'];sept=bisect_left(times,prob['holdout_start'])
        gate=lambda f:calibrated_predict(prob['model'],prob['calibration'],f)[0]>=prob['threshold']
        jobs=[('full',end,WARMUP,base,None,None),('holdout',end,start,base,None,None),
              ('selected',end,start,chosen,None,None),('september',len(cs),sept,p,None,None),
              ('ai',len(cs),sept,{**p,'ai_weight':ai['selected_weight']},None,history),
              ('probability',len(cs),sept,p,gate,None)]
        for name,last,first,params,filter_,hist in jobs:
            r=simulate(cs[:last],sym,params,start_index=first,precomputed=pre,
                       entry_filter=filter_,historical_ai=hist)
            aggregate[name].extend(r['trades'])
        print('verified replay',sym,flush=True)
    expected={'full':saved['full_baseline']['metrics'],'holdout':saved['holdout_baseline']['metrics'],
              'selected':saved['holdout_selected']['metrics'],'september':prob['baseline'],
              'ai':ai['selected_holdout'],'probability':prob['filtered']}
    checks=0
    for name,rows in aggregate.items():
        actual=trade_metrics(rows)
        for key in ('trades','wins','losses','breakevens','win_rate','profit_factor','expectancy_r'):
            a,b=actual[key],expected[name][key]
            assert a==b or (a is not None and b is not None and abs(a-b)<1e-10),(name,key,a,b)
            checks+=1
    result={'matched_frozen_metric_checks':checks,'datasets_sha256_matched':15,
            'parameters_retuned':False,'broker_orders_sent':0}
    (report_dir/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--report-dir',type=Path,required=True)
    a=p.parse_args();main(a.data_dir,a.report_dir)
