"""Подписки: состояния, права и то, что администратор может сделать.

Проверяется ровно то, на чём продукт ломается молча: что приостановленная
подписка не торгует, что ответ администратора не содержит пароля брокера, и
что продление считается от конца периода, а не от сегодня.
"""

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.billing.plans import DEFAULT_ENTITLEMENTS, allows, merged_entitlements
from app.billing.service import (
    days_left,
    effective_status,
    entitlements_for,
    extend,
    seed_plans,
    start_subscription,
    subscription_view,
)
from app.database import Base
from app.models import Plan, Subscription, User


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _user(db: Session, name: str = "trader") -> User:
    user = User(username=name, password_hash="x", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class EntitlementTest(unittest.TestCase):
    def test_unknown_keys_are_dropped_and_missing_ones_default(self):
        merged = merged_entitlements({"autotrade": True, "wat": 1})
        self.assertTrue(merged["autotrade"])
        self.assertNotIn("wat", merged)
        self.assertEqual(merged["max_instruments"], DEFAULT_ENTITLEMENTS["max_instruments"])

    def test_minus_one_means_no_limit_and_zero_means_forbidden(self):
        self.assertTrue(allows({"max_open_signals": -1}, "max_open_signals", 10_000))
        self.assertFalse(allows({"max_open_signals": 0}, "max_open_signals", 1))
        self.assertTrue(allows({"max_open_signals": 5}, "max_open_signals", 5))
        self.assertFalse(allows({"max_open_signals": 5}, "max_open_signals", 6))


class StatusTest(unittest.TestCase):
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)

    def _sub(self, end_offset_days: float, **kw) -> Subscription:
        return Subscription(
            user_id=1,
            plan_code="pro",
            current_period_end=self.now + timedelta(days=end_offset_days),
            grace_days=kw.pop("grace_days", 3),
            status=kw.pop("status", "active"),
            trial=kw.pop("trial", 0),
        )

    def test_inside_the_period_is_active_and_a_trial_says_so(self):
        self.assertEqual(effective_status(self._sub(5), self.now), "active")
        self.assertEqual(effective_status(self._sub(5, trial=1), self.now), "trialing")

    def test_grace_window_is_past_due_then_suspended(self):
        self.assertEqual(effective_status(self._sub(-1), self.now), "past_due")
        self.assertEqual(effective_status(self._sub(-2.9), self.now), "past_due")
        self.assertEqual(effective_status(self._sub(-4), self.now), "suspended")

    def test_a_manual_decision_wins_over_the_dates(self):
        # администратор приостановил вручную — даты этого не отменяют
        self.assertEqual(effective_status(self._sub(30, status="suspended"), self.now), "suspended")
        self.assertEqual(effective_status(self._sub(30, status="cancelled"), self.now), "cancelled")

    def test_no_subscription_reads_as_expired(self):
        self.assertEqual(effective_status(None, self.now), "expired")

    def test_days_left_rounds_away_from_zero(self):
        # «остался час» — это ещё день, иначе интерфейс скажет «0 дней» тому,
        # у кого ещё есть время
        self.assertEqual(days_left(self._sub(0.04), self.now), 1)
        self.assertEqual(days_left(self._sub(-0.04), self.now), -1)
        self.assertEqual(days_left(self._sub(5), self.now), 5)


class AccessTest(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        seed_plans(self.db)
        self.user = _user(self.db)

    def tearDown(self):
        self.db.close()

    def test_an_active_pro_subscription_grants_the_plan_rights(self):
        start_subscription(self.db, self.user.id, "pro")
        rights = entitlements_for(self.db, self.user)
        self.assertTrue(rights["autotrade"])
        self.assertTrue(rights["mt5"])
        self.assertEqual(rights["max_instruments"], 40)

    def test_a_suspended_subscription_grants_nothing_new(self):
        sub = start_subscription(self.db, self.user.id, "pro")
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=30)
        self.db.commit()

        rights = entitlements_for(self.db, self.user)
        self.assertFalse(rights["autotrade"])
        self.assertFalse(rights["mt5"])
        self.assertEqual(rights["max_instruments"], 0)
        self.assertEqual(rights["max_open_signals"], 0)

    def test_a_user_without_any_subscription_gets_nothing(self):
        rights = entitlements_for(self.db, self.user)
        self.assertFalse(rights["autotrade"])
        self.assertEqual(rights["max_open_signals"], 0)

    def test_the_view_tells_the_front_end_what_to_show(self):
        start_subscription(self.db, self.user.id, "pro")
        view = subscription_view(self.db, self.user)
        self.assertTrue(view["active"])
        self.assertEqual(view["notice"], "none")
        self.assertEqual(view["plan"]["code"], "pro")

        sub = self.db.query(Subscription).first()
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=2)
        self.db.commit()
        self.assertEqual(subscription_view(self.db, self.user)["notice"], "due_soon")

        sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=1)
        self.db.commit()
        self.assertEqual(subscription_view(self.db, self.user)["notice"], "past_due")

        sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=30)
        self.db.commit()
        view = subscription_view(self.db, self.user)
        self.assertEqual(view["notice"], "blocked")
        self.assertTrue(view["read_only"])


class ExtendTest(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        seed_plans(self.db)
        self.user = _user(self.db)

    def tearDown(self):
        self.db.close()

    def test_extension_starts_at_the_end_of_the_period_not_today(self):
        sub = start_subscription(self.db, self.user.id, "pro", days=10)
        before = sub.current_period_end
        extend(self.db, sub, 30)
        # иначе оплата за три дня до конца съедала бы эти три дня
        self.assertAlmostEqual(
            (sub.current_period_end - before).total_seconds(), 30 * 86400, delta=5
        )

    def test_extending_an_expired_subscription_starts_from_today_and_revives_it(self):
        sub = start_subscription(self.db, self.user.id, "pro", days=10)
        sub.current_period_end = datetime.now(timezone.utc) - timedelta(days=40)
        sub.status = "suspended"
        self.db.commit()

        extend(self.db, sub, 30)
        self.assertEqual(effective_status(sub), "active")
        self.assertGreater(days_left(sub), 29)

    def test_seeding_plans_twice_does_not_overwrite_an_edited_price(self):
        plan = self.db.get(Plan, "pro")
        plan.price_cents = 12345
        self.db.commit()

        self.assertEqual(seed_plans(self.db), 0)
        self.assertEqual(self.db.get(Plan, "pro").price_cents, 12345)


if __name__ == "__main__":
    unittest.main()
