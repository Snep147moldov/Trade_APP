import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backtest import engine as bt
from app.backtest.probability import fit, predict
from app.config import DEFAULT_SETTINGS
from app.database import Base
from app.indicators import core as ind
from app.models import Signal, Setting
from app.performance import closed_sample, trade_metrics
from app.risk.calculator import position_size
from app.risk.manager import _kelly_fraction, evaluate
from app.risk.limits import current_equity
from app.services.analysis import _htf_trend
from app.services.candles import _resample, is_simulated, market_data_issues
from app.services.journal import journal_stats
from app.services.tracking import _apply_outcome, signal_stats
from app.signals.engine import INVERTED_SIGNS, compute_indicators, score_components
from app.tools.factors import _spearman


def candles(n=210):
    start = 1767225600
    return [dict(time=start + i * 3600, open=1.0, high=1.001, low=.999,
                 close=1.0, complete=True, volume=100) for i in range(n)]


def pre(n):
    arrays = {k: np.full(n, value) for k, value in {
        'close': 1., 'high': 1.001, 'low': .999, 'ema20': 1., 'ema50': 1.,
        'rsi14': 50., 'macd_hist': 0., 'pct_b': .5, 'atr14': .01,
        'stoch_k': 50., 'stoch_d': 50., 'adx14': 25., 'roc10': 0.,
        'hurst': .5, 'er': .2, 'er_sign': 1., 'tsmom': 0.}.items()}
    return arrays


def simulate(cs, side=1, **params):
    with patch.object(bt, 'score_components', return_value=({}, {}, side * .5, 'trending')):
        return bt.simulate(cs, 'EUR_USD', {'sl_atr_multiple': 2., 'spread_pips': 0.,
            'slippage_pips': 0., 'cooldown_bars': 1000, **params}, precomputed=pre(len(cs)))


class IndicatorsTest(unittest.TestCase):
    def test_rsi_flat_rising_falling(self):
        self.assertEqual(ind.rsi(np.ones(40))[-1], 50)
        self.assertEqual(ind.rsi(np.arange(1., 41.))[-1], 100)
        self.assertEqual(ind.rsi(np.arange(40., 0., -1.))[-1], 0)

    def test_wilder_seed_and_recursion(self):
        np.testing.assert_allclose(ind._wilder_smooth(np.array([1., 2., 3., 6.]), 3)[2:], [2., 10/3])

    def test_sma_preserves_missing_observations_and_recovers(self):
        out = ind.sma(np.array([np.nan, 1., 2., 3., np.nan, 5., 6., 7.]), 3)
        self.assertTrue(np.isnan(out[2]))
        self.assertEqual(out[3], 2)
        self.assertEqual(out[7], 6)

    def test_stochastic_real_warmup(self):
        close = np.arange(1., 41.)
        k, d = ind.stochastic(close + 1, close - 1, close)
        self.assertEqual(np.flatnonzero(np.isfinite(k))[0], 15)
        self.assertEqual(np.flatnonzero(np.isfinite(d))[0], 17)

    def test_adx_flat_is_zero(self):
        a, p, m = ind.adx(np.ones(50), np.ones(50), np.ones(50))
        self.assertEqual(a[-1], 0)
        self.assertEqual(p[-1], 0)
        self.assertEqual(m[-1], 0)

    def test_indicator_prefix_invariance_and_live_parity(self):
        cs = candles(250)
        for i, c in enumerate(cs):
            c['close'] = 1 + .0005 * np.sin(i / 7)
        full = bt._precompute(cs)
        prefix = bt._precompute(cs[:230])
        live = compute_indicators(cs[:230])
        snap = bt._snap(full, 229)
        for key in full:
            np.testing.assert_allclose(full[key][:230], prefix[key], equal_nan=True, atol=1e-12)
        for key in snap:
            self.assertAlmostEqual(snap[key], live[key], places=10, msg=key)

    def test_spearman_ties_and_constant(self):
        self.assertEqual(_spearman(np.ones(50), np.arange(50.)), 0.)
        x = np.repeat(np.arange(10.), 5)
        self.assertAlmostEqual(_spearman(x, -x), -1.)

    def test_weights_ai_cap_and_signed_reconstruction(self):
        snap = bt._snap(pre(1), 0)
        snap.update(adx14=5., hurst=.4, rsi14=80., er_signed=.3)
        comp, weights, score, _ = score_components(snap, 1., 1., 18,
            ai_weight=.15, factor_signs=INVERTED_SIGNS,
            factor_mults={'trend': 1000., 'bollinger': -100.})
        self.assertAlmostEqual(sum(weights.values()), 1.)
        self.assertAlmostEqual(weights['ai_news'] + weights['ai_prediction'], .15)
        self.assertAlmostEqual(score, sum(comp[k] * w for k, w in weights.items()))
        self.assertTrue(all(w >= 0 for w in weights.values()))

    def test_regime_candidate_no_implicit_inversion(self):
        snap = bt._snap(pre(1), 0)
        snap.update(adx14=5., rsi14=80., pct_b=1.2)
        _, weights, score, _ = score_components(snap, 0., 0., 18, ai_weight=0,
                                                 strategy_variant='regime_balanced')
        self.assertLess(score, 0)
        self.assertAlmostEqual(sum(weights.values()), 1)
        with self.assertRaises(ValueError):
            score_components(snap, 0, 0, 18, factor_signs=INVERTED_SIGNS,
                             strategy_variant='regime_balanced')


class ExecutionTest(unittest.TestCase):
    def test_next_open_entry_and_same_bar_stop(self):
        cs = candles()
        cs[200].update(open=1.05, close=1.05, high=1.06, low=1.02)
        t = simulate(cs)['trades'][0]
        self.assertEqual(t['entry'], 1.05)
        self.assertEqual(t['entry_time'], cs[200]['time'])
        self.assertEqual(t['signal_time'], cs[199]['time'])
        self.assertEqual(t['exit_time'], cs[200]['time'])
        self.assertAlmostEqual(t['r'], -1.)

    def test_both_levels_hit_stop_first_long_and_short(self):
        cs = candles()
        cs[200].update(high=1.1, low=.9)
        for side in (1, -1):
            t = simulate(cs, side)['trades'][0]
            self.assertEqual(t['status'], 'hit_sl')
            self.assertAlmostEqual(t['r'], -1.)

    def test_known_takeprofit_gap_precedes_later_stop(self):
        cs = candles()
        cs[201].update(open=1.06, high=1.07, low=.9, close=1.)
        t = simulate(cs)['trades'][0]
        self.assertEqual(t['status'], 'hit_tp')
        self.assertAlmostEqual(t['r'], 1.8)

    def test_stop_gap_can_exceed_one_r(self):
        cs = candles()
        cs[201].update(open=.94, high=.96, low=.93, close=.95)
        self.assertAlmostEqual(simulate(cs)['trades'][0]['r'], -3.)

    def test_terminal_positions_are_settled_with_costs(self):
        t = simulate(candles(), spread_pips=2., slippage_pips=.5, commission_eur=2.)['trades'][0]
        expected_value_per_price = (100 - 2) / (.02 + .00005)
        expected_pnl = -.0003 * expected_value_per_price - 2
        self.assertEqual(t['status'], 'end_of_data')
        self.assertAlmostEqual(t['pnl_eur'], expected_pnl)
        self.assertAlmostEqual(t['r'], expected_pnl / 100)

    def test_initial_stop_risk_includes_commission_and_slippage(self):
        cs = candles()
        cs[200].update(low=.97)
        t = simulate(cs, spread_pips=2., slippage_pips=.5, commission_eur=2.)['trades'][0]
        self.assertAlmostEqual(t['pnl_eur'], -100.)
        self.assertAlmostEqual(t['r'], -1.)

    def test_historical_bid_ask_override_assumed_spread(self):
        cs = candles()
        for c in cs:
            for k in ('open','high','low','close'):
                c['bid_'+k] = c[k] - .0001
                c['ask_'+k] = c[k] + .0001
        t = simulate(cs, spread_pips=100.)['trades'][0]
        self.assertAlmostEqual(t['entry'], 1.0001)
        self.assertAlmostEqual(t['exit'], .9999)

    def test_drawdown_includes_unrealized_loss(self):
        cs = candles()
        cs[201].update(close=.99, low=.99)
        r = simulate(cs)
        self.assertGreater(r['metrics']['max_drawdown_pct'], 0)
        self.assertEqual(r['metrics']['realized_max_drawdown_pct'], 0)

    def test_breakeven_does_not_use_same_bar_future(self):
        cs = candles()
        cs[200].update(high=1.025, low=.99, close=1.01)
        cs[201].update(low=.995, close=1.)
        t = simulate(cs, breakeven_at_r=1.)['trades'][0]
        self.assertEqual(t['exit_time'], cs[201]['time'])
        self.assertEqual(t['status'], 'hit_sl')
        self.assertAlmostEqual(t['r'], 0.)

    def test_partial_profit_is_net_weighted(self):
        cs = candles()
        cs[200].update(high=1.025, close=1.01)
        cs[201].update(low=.97)
        t = simulate(cs, partial_tp_enabled=True, partial_tp_fraction=.6)['trades'][0]
        self.assertAlmostEqual(t['r'], .2)

    def test_zero_is_not_a_loss_and_subcent_profit_is_a_win(self):
        m = trade_metrics([dict(pnl_eur=x, r=x) for x in (0, .001, -1)])
        self.assertEqual((m['wins'], m['losses'], m['breakevens']), (1, 1, 1))
        self.assertAlmostEqual(m['expectancy_r'], -.999 / 3)

    def test_entry_filter_runs_before_position_allocation(self):
        cs = candles()
        with patch.object(bt, 'score_components', return_value=({}, {}, .5, 'trending')):
            r = bt.simulate(cs, 'EUR_USD', {}, precomputed=pre(len(cs)), entry_filter=lambda x: False)
        self.assertEqual(r['metrics']['trades'], 0)

    def test_input_validation(self):
        for bad in ([], candles(200), [{**c, 'complete': False} for c in candles()]):
            with self.assertRaises(ValueError):
                simulate(bad)
        cs = candles()
        cs[-1]['time'] = cs[-2]['time']
        with self.assertRaises(ValueError):
            simulate(cs)
        for params in ({'commission_eur': -1}, {'min_score': float('nan')},
                       {'slippage_pips': float('inf')}, {'risk_per_trade_pct': 0}):
            with self.assertRaises(ValueError):
                simulate(candles(), **params)

    def test_walk_forward_disjoint_and_compounds(self):
        cs = candles(1000)
        with patch.object(bt, '_precompute', return_value=pre(len(cs))), \
             patch.object(bt, 'score_components', return_value=({}, {}, .5, 'trending')):
            wf = bt._walk_forward(cs, 'EUR_USD', {**bt.DEFAULT_PARAMS, 'expiry_bars': 4}, 3)
        folds = wf['folds']
        for i, f in enumerate(folds):
            self.assertLess(f['train_to'], f['test_from'])
            self.assertEqual(f['test']['period']['from'], f['test_from'])
            if i:
                self.assertLess(folds[i-1]['test_to'], f['test_from'])
        self.assertEqual(folds[-1]['test_to'], cs[-1]['time'])
        self.assertAlmostEqual(wf['oos_pnl_eur'], folds[-1]['test']['final_equity'] - 10000, places=2)


class DataTest(unittest.IsolatedAsyncioTestCase):
    def test_resampling_preserves_provenance_and_completeness(self):
        cs = [{**c, 'time': i*300, 'simulated': True} for i, c in enumerate(candles(10))]
        result = _resample(cs, 2400)
        self.assertTrue(result[0]['complete'])
        self.assertFalse(result[1]['complete'])
        self.assertTrue(is_simulated(result))
        self.assertFalse(_resample(cs[1:8], 2400)[0]['complete'])

    def test_fx_saturday_movement_rejected_crypto_exempt(self):
        cs = [{**candles(1)[0], 'time': int(datetime(2026,9,12,12,tzinfo=timezone.utc).timestamp())}]
        self.assertTrue(market_data_issues(cs, 'EUR_USD', '1h'))
        self.assertFalse(market_data_issues(cs, 'BTC_USD', '1h'))

    async def test_htf_rejects_synthetic_and_forming(self):
        for cs in ([{**c, 'simulated': True} for c in candles(120)],
                   [{**c, 'complete': False} for c in candles(120)]):
            with patch('app.services.analysis.get_candles', AsyncMock(return_value=cs)):
                _, score = await _htf_trend({}, 'EUR_USD', '1h')
            self.assertIsNone(score)


class MoneyTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, money=0., broker=False, broker_pnl=None, status='hit_sl'):
        s = Signal(instrument='EUR_USD', timeframe='1h', direction='BUY', entry=1.,
                   stop_loss=.98, take_profit=1.036, risk_reward=1.8, units=1000,
                   risk_amount=10., score=.5, confidence=.8, components={},
                   status=status, pnl_money=money, pnl_pips=99., mt5_orders=int(broker),
                   mt5_pnl=broker_pnl, resolved_at=datetime(2026,1,2),
                   created_at=datetime(2026,1,1), strategy='audit')
        self.db.add(s)
        self.db.commit()
        return s

    def test_broker_and_paper_not_mixed(self):
        self.add(1000)
        self.add(100, True, -10)
        self.add(-100, True, 20)
        self.add(0, True, 0)
        self.add(0, True, None)
        for m in (journal_stats(self.db, 1000), signal_stats(self.db, 1000)):
            self.assertEqual((m['closed'], m['wins'], m['losses'], m['breakevens']), (3,1,1,1))
            self.assertEqual(m['source'], 'broker')
            self.assertEqual(m['win_rate'], 33.3)
            self.assertEqual(m['excluded_closed'], 2)

    def test_kelly_uses_net_r_and_does_not_fallback_at_zero_edge(self):
        for _ in range(20):
            self.add(money=100, broker=True, broker_pnl=-10)
        fraction, win_rate = _kelly_fraction(self.db, 1.8)
        self.assertEqual((fraction, win_rate), (0., 0.))
        st = {**DEFAULT_SETTINGS, 'sizing_mode': 'half_kelly', 'weekend_guard_min': 0,
              'daily_cutoff_hour': 0, 'max_currency_risk_pct': 0}
        levels = dict(entry=1., stop_loss=.98, take_profit=1.036, sl_distance=.02, tp_distance=.036)
        r = evaluate(self.db, 'EUR_USD', '1h', 'BUY', .5, bt._snap(pre(1),0), levels, st)
        self.assertEqual(r['risk_amount'], 0.)
        self.assertFalse(r['approved'])
        self.assertTrue(any('Kelly' in x for x in r['reasons']))

    def test_zero_broker_balance_is_authoritative(self):
        with patch('app.services.mt5_sync.get_state', return_value={'connected': True, 'balance': 0.}):
            self.assertEqual(current_equity(self.db, DEFAULT_SETTINGS), 0.)

    def test_position_size_fractional_units_and_net_profit(self):
        r = position_size(instrument='XAU_USD', balance_eur=100, risk_pct=1,
                          entry=2400, stop_loss=2390, commission_eur=.1, spread_pips=0,
                          eur_per_quote=1., risk_reward=2.)
        self.assertAlmostEqual(r['units'], .09)
        self.assertAlmostEqual(r['potential_profit_eur'], 1.7)
        self.assertFalse(position_size(instrument='EUR_USD', balance_eur=100, risk_pct=1,
                                      entry=1., stop_loss=.99, eur_per_quote=0)['ok'])

    def test_partial_pips_match_weighted_money(self):
        s = self.add()
        _apply_outcome(s, dict(exit=.98, partial_frac=.6, partial_taken=True,
                              partial_r=1., status='hit_sl', be_moved=False, eff_sl=.98))
        self.assertAlmostEqual(s.pnl_money, 2.)
        self.assertGreater(s.pnl_pips, 0)

    def test_cost_gate_counts_full_spread_once_and_zero_disables(self):
        st = {**DEFAULT_SETTINGS, 'weekend_guard_min': 0, 'daily_cutoff_hour': 0,
              'max_currency_risk_pct': 0, 'max_cost_ratio': .25}
        levels = dict(entry=1., stop_loss=.98, take_profit=1.036, sl_distance=.02, tp_distance=.036)
        for spread, limit in ((.004, .25), (0., .01), (.02, 0.)):
            r = evaluate(self.db, 'EUR_USD', '1h', 'BUY', .5, bt._snap(pre(1),0),
                         levels, {**st, 'max_cost_ratio': limit}, broker_spread=spread)
            self.assertFalse(any('спред' in x for x in r['reasons']))

    def test_new_position_included_in_risk_cap(self):
        st = {**DEFAULT_SETTINGS, 'risk_per_trade_pct': 2., 'max_open_risk_pct': .1,
              'max_currency_risk_pct': 0, 'weekend_guard_min': 0, 'daily_cutoff_hour': 0}
        levels = dict(entry=1., stop_loss=.98, take_profit=1.036, sl_distance=.02, tp_distance=.036)
        r = evaluate(self.db, 'EUR_USD', '1h', 'BUY', .5, bt._snap(pre(1),0), levels, st)
        self.assertFalse(r['approved'])
        self.assertTrue(any('с новой сделкой' in x for x in r['reasons']))

    def test_missing_broker_balance_does_not_create_paper_bankroll(self):
        with patch('app.services.runtime.get_credentials', return_value={
                'metaapi_token': 'test', 'mt5_account_id': 'test'}):
            self.assertEqual(current_equity(self.db, DEFAULT_SETTINGS), 0.)


class ProbabilityTest(unittest.TestCase):
    def test_regularized_model_predicts_monotonic_and_is_immutable(self):
        x = np.linspace(-2, 2, 200)[:, None]
        y = (x[:, 0] > .2).astype(int)
        m = fit(x[:150], y[:150])
        saved = copy.deepcopy(m)
        p = predict(m, x)
        self.assertTrue(np.all(np.diff(p) > 0))
        self.assertTrue(np.all((p > 0) & (p < 1)))
        self.assertEqual(m, saved)
        self.assertAlmostEqual(m['center'][0], x[:150].mean())

    def test_no_fitting_on_missing_or_single_class_outcomes(self):
        with self.assertRaises(ValueError):
            fit(np.ones((50,2)), np.ones(50))


if __name__ == '__main__':
    unittest.main()
