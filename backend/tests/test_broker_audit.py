import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.backtest.ai_history import AIHistory
from app.database import Base
from app.models import BrokerDeal, Signal
from app.services import mt5, mt5_sync


class HistoryTest(unittest.TestCase):
    def test_ai_only_available_after_recording_and_decays(self):
        ts = datetime(2026, 7, 1, tzinfo=timezone.utc)
        h = AIHistory([{'created_at': ts, 'vector': {'EUR': .7, 'USD': -.7},
                        'pair_biases': {'EUR_USD': {'bias': -.8}}},
                       {'created_at': ts + timedelta(days=2), 'vector': {'EUR': -1}}])
        self.assertEqual(h.at(ts.timestamp() - 1, 'EUR_USD'), (0., 0., False))
        self.assertEqual(h.at(ts.timestamp(), 'EUR_USD'), (1., -.8, True))
        self.assertEqual(h.at(ts.timestamp() + 43200, 'EUR_USD'), (.5, -.4, True))

    def test_owned_signal_comments_only(self):
        for text in ('#123', 'OtherEA #123', 'NotFXNav #123', 'FXNavigation #123'):
            self.assertIsNone(mt5_sync._sig_id(text))
        # прежние имена приложения по-прежнему считаются своими: позиции,
        # открытые до переименований, висят у брокера с ними
        for text in ('FXNav #123', 'FXNav auto #123 (2/3)',
                     'Aurex #123', 'Codnixy #123'):
            self.assertEqual(mt5_sync._sig_id(text), 123)


class BrokerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.sig = Signal(instrument='EUR_USD', timeframe='1h', direction='BUY',
                          entry=1., stop_loss=.98, take_profit=1.036, risk_reward=1.8,
                          units=1000, risk_amount=10., score=.5, confidence=.8,
                          components={}, status='open', mt5_orders=1,
                          created_at=datetime.now(timezone.utc) - timedelta(days=30))
        self.db.add(self.sig)
        self.db.commit()
        self.creds = {'metaapi_token': 'test', 'mt5_account_id': 'test-account'}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def deal(self, ticket, entry, net=0, volume=.1, days=0, comment=None):
        return dict(id=ticket, orderId=ticket, positionId='p1', type='DEAL_TYPE_BUY',
                    entryType='DEAL_ENTRY_' + entry, profit=net, commission=-.5,
                    volume=volume, time=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(),
                    comment=comment if comment is not None else f'FXNav #{self.sig.id}')

    async def tick(self, deals, positions=None, failed=False):
        pos = {'ok': False} if failed else {'ok': True, 'positions': positions or []}
        with patch.object(mt5_sync, 'get_credentials', return_value=self.creds), \
             patch.object(mt5_sync, 'get_app_config', return_value={'telegram_enabled': False}), \
             patch.object(mt5, 'account_information', AsyncMock(return_value={'ok': False})), \
             patch.object(mt5, 'positions', AsyncMock(return_value=pos)), \
             patch.object(mt5, 'history_deals', AsyncMock(return_value={'ok': True, 'deals': deals})):
            await mt5_sync.sync_tick(self.db)
        self.db.refresh(self.sig)

    async def test_positions_failure_does_not_close_trade(self):
        await self.tick([self.deal('1', 'IN'), self.deal('2', 'OUT', 5)], failed=True)
        self.assertEqual(self.sig.status, 'open')
        self.assertEqual(self.sig.mt5_pnl, 4.)

    async def test_entry_fees_net_zero_and_actual_close_date(self):
        deals = [self.deal('1', 'IN', days=20), self.deal('2', 'OUT', 1., days=2)]
        await self.tick(deals)
        self.assertEqual(self.sig.mt5_pnl, 0.)
        self.assertNotEqual(self.sig.status, 'open')
        self.assertAlmostEqual(self.sig.resolved_at.replace(tzinfo=timezone.utc).timestamp(),
                               mt5_sync._deal_ts(deals[-1]), places=3)

    async def test_partial_history_survives_rolling_window_and_is_idempotent(self):
        entry = self.deal('1', 'IN', days=20)
        out1 = self.deal('2', 'OUT', 5, volume=.05, days=10)
        await self.tick([entry, out1], positions=[{'id':'p1','profit':2,'comment':''}])
        self.assertEqual(self.sig.status, 'open')
        out2 = self.deal('3', 'OUT', -2, volume=.05)
        await self.tick([out2])
        await self.tick([out2])
        self.assertEqual(self.sig.mt5_pnl, 1.5)
        self.assertEqual(self.sig.mt5_orders, 1)
        self.assertEqual(len(self.db.scalars(select(BrokerDeal)).all()), 3)

    async def test_foreign_comment_does_not_settle_signal(self):
        await self.tick([self.deal('1', 'IN', comment=f'OtherEA #{self.sig.id}'),
                         self.deal('2', 'OUT', 50, comment='')])
        self.assertEqual(self.sig.status, 'open')
        self.assertIsNone(self.sig.mt5_pnl)

    async def test_partial_exit_without_position_snapshot_match_stays_open(self):
        await self.tick([self.deal('1', 'IN'), self.deal('2', 'OUT', 5, volume=.05)])
        self.assertEqual(self.sig.status, 'open')

    async def test_stale_signal_rejected_before_trade_api(self):
        q = AsyncMock(return_value={'ok': True, 'bid': 1.009, 'ask': 1.01})
        api = AsyncMock()
        with patch.object(mt5, 'get_credentials', return_value=self.creds), \
             patch.object(mt5, 'symbol_price', q), patch.object(mt5, '_api', api), \
             patch('app.services.settings.settings_for_instrument', return_value={'max_entry_drift_r':.25}):
            result = await mt5.place_order(self.db, 'EUR_USD', 'BUY', .01, .98, 1.036,
                                            expected_entry=1.)
        self.assertFalse(result['ok'])
        self.assertIn('0.50R', result['error'])
        q.assert_awaited_once_with(self.db, 'EUR_USD', fresh=True)
        api.assert_not_awaited()

    async def test_nonfinite_order_rejected(self):
        with patch.object(mt5, 'get_credentials', return_value=self.creds):
            for values in ({'lots': float('nan')}, {'lots': .01, 'stop_loss': float('inf')}):
                result = await mt5.place_order(self.db, 'EUR_USD', 'BUY', **values)
                self.assertFalse(result['ok'])

    async def test_history_paginates_and_fails_closed_on_missing_page(self):
        page = [{'id': str(i)} for i in range(1000)]
        with patch.object(mt5, 'get_credentials', return_value=self.creds), \
             patch.object(mt5, '_fresh_region', AsyncMock(return_value='new-york')), \
             patch.object(mt5, '_api', AsyncMock(side_effect=[{'ok':True,'data':page},
                                                              {'ok':True,'data':[{'id':'last'}]}])) as api:
            result = await mt5.history_deals(self.db, 'start', 'end')
        self.assertEqual(len(result['deals']), 1001)
        self.assertIn('offset=1000', api.await_args_list[1].args[1])
        with patch.object(mt5, 'get_credentials', return_value=self.creds), \
             patch.object(mt5, '_fresh_region', AsyncMock(return_value='new-york')), \
             patch.object(mt5, '_api', AsyncMock(side_effect=[{'ok':True,'data':page}, {'ok':False}])):
            self.assertFalse((await mt5.history_deals(self.db, 'start', 'end'))['ok'])


if __name__ == '__main__':
    unittest.main()
