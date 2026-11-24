"""События оплат maib (их шлёт витрина): аккаунт, срок, состояние, история, письма.

Проверяется то, на чём платный доступ ломается молча: повтор события не
создаёт второй аккаунт, вторую оплату или второе письмо, старое событие после
нового не откатывает отмену, отменённая подписка дорабатывает оплаченный срок,
аккаунт администратора провайдер не трогает, а подтверждение оплаты (его
требует maib) уходит после каждого списания.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import config
from app.billing import provider
from app.billing.links import account_token, verify_account
from app.billing.provider import DUNNING_GRACE_DAYS, ProviderEvent, apply_event
from app.billing.service import effective_status, get_subscription, seed_plans, subscription_view
from app.database import Base
from app.models import Payment, Subscription, User


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    seed_plans(db)
    return db


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _sub_event(status: str = "active", *, updated: datetime = NOW, **kw) -> ProviderEvent:
    base = dict(
        event="subscription_created",
        kind="subscription",
        object_id="9b2f0c4e-0000-4000-8000-000000000901",
        subscription_id="9b2f0c4e-0000-4000-8000-000000000901",
        customer_id="buyer@example.com",
        email="Buyer@Example.com",
        plan="pro",
        interval="month",
        status=status,
        renews_at=_iso(NOW + timedelta(days=30)),
        updated_at=_iso(updated),
        locale="de",
        manage_url="https://fxnavigator.net/de/billing?token=abc",
    )
    base.update(kw)
    return ProviderEvent(**base)


def _pay_event(event: str = "subscription_payment_success", **kw) -> ProviderEvent:
    base = dict(
        event=event,
        kind="payment",
        object_id="c0ffee00-0000-4000-8000-000000005501",
        subscription_id="9b2f0c4e-0000-4000-8000-000000000901",
        email="buyer@example.com",
        status="paid",
        amount_cents=4900,
        currency="eur",
        billing_reason="initial",
        order_no="C0FFEE00",
        description="FX Navigator Premium, 1 month",
        merchant="IGBFXNavigator S.R.L., IDNO 1026023163277",
        card="510218******1124",
        rrn="331711380059",
        approval="327593",
        paid_at=_iso(NOW),
        next_charge_at=_iso(NOW + timedelta(days=30)),
        manage_url="https://fxnavigator.net/de/billing?token=abc",
    )
    base.update(kw)
    return ProviderEvent(**base)


class SubscriptionEventTest(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        patcher = mock.patch.object(provider, "send_email", return_value=True)
        self.send_email = patcher.start()
        self.addCleanup(patcher.stop)

    def test_purchase_creates_account_and_active_subscription(self):
        out = apply_event(self.db, _sub_event())
        self.assertTrue(out["ok"])
        self.assertTrue(out["created"])

        user = self.db.scalar(select(User))
        self.assertEqual(user.username, "buyer@example.com")
        self.assertEqual(user.email, "buyer@example.com")
        self.assertEqual(user.language, "de")
        self.assertEqual(user.role, "user")

        sub = get_subscription(self.db, user.id)
        self.assertEqual(sub.plan_code, "pro")
        self.assertEqual(sub.provider, "maib")
        self.assertEqual(sub.external_id, "9b2f0c4e-0000-4000-8000-000000000901")
        self.assertEqual(sub.customer_ref, "buyer@example.com")
        self.assertEqual(sub.manage_url, "https://fxnavigator.net/de/billing?token=abc")
        self.assertEqual(sub.billing_interval, "month")
        self.assertEqual(effective_status(sub), "active")
        self.send_email.assert_called_once()

    def test_replayed_event_does_not_duplicate_account_or_mail(self):
        apply_event(self.db, _sub_event())
        out = apply_event(self.db, _sub_event(event="subscription_updated"))
        self.assertFalse(out["created"])
        self.assertEqual(len(self.db.scalars(select(User)).all()), 1)
        self.assertEqual(len(self.db.scalars(select(Subscription)).all()), 1)
        self.send_email.assert_called_once()

    def test_existing_account_is_matched_by_email_case_insensitively(self):
        self.db.add(User(username="trader", password_hash="x", role="user", email="buyer@example.com"))
        self.db.commit()
        out = apply_event(self.db, _sub_event())
        self.assertFalse(out["created"])
        self.assertEqual(len(self.db.scalars(select(User)).all()), 1)
        self.send_email.assert_not_called()

    def test_stale_event_does_not_undo_cancellation(self):
        apply_event(self.db, _sub_event(updated=NOW))
        ends = NOW + timedelta(days=12)
        apply_event(self.db, _sub_event(
            "cancelled", event="subscription_cancelled", ends_at=_iso(ends),
            updated=NOW + timedelta(minutes=5)))
        # повтор доставки subscription_created, который опоздал
        out = apply_event(self.db, _sub_event(updated=NOW))
        self.assertTrue(out.get("stale"))
        sub = self.db.scalar(select(Subscription))
        self.assertEqual(sub.cancel_at_period_end, 1)

    def test_cancelled_keeps_access_until_ends_at_then_stops(self):
        apply_event(self.db, _sub_event())
        ends = NOW + timedelta(days=12)
        apply_event(self.db, _sub_event(
            "cancelled", event="subscription_cancelled", ends_at=_iso(ends),
            updated=NOW + timedelta(minutes=1)))
        sub = self.db.scalar(select(Subscription))
        self.assertEqual(effective_status(sub, NOW + timedelta(days=11)), "active")
        self.assertEqual(effective_status(sub, ends + timedelta(hours=1)), "suspended")

        apply_event(self.db, _sub_event(
            "expired", event="subscription_expired", ends_at=_iso(ends),
            updated=NOW + timedelta(days=12, minutes=1)))
        self.assertEqual(effective_status(sub, ends + timedelta(hours=1)), "cancelled")

    def test_past_due_keeps_access_while_provider_retries(self):
        apply_event(self.db, _sub_event(renews_at=_iso(NOW - timedelta(days=1))))
        apply_event(self.db, _sub_event(
            "past_due", event="subscription_updated",
            renews_at=_iso(NOW + timedelta(days=3)), updated=NOW + timedelta(minutes=1)))
        sub = self.db.scalar(select(Subscription))
        self.assertEqual(sub.grace_days, DUNNING_GRACE_DAYS)
        # срок не сдвинут на дату следующей попытки списания
        self.assertEqual(effective_status(sub), "past_due")

        apply_event(self.db, _sub_event(
            "unpaid", event="subscription_updated", updated=NOW + timedelta(minutes=2)))
        self.assertEqual(effective_status(sub), "suspended")

    def test_renewal_moves_period_end(self):
        apply_event(self.db, _sub_event())
        later = NOW + timedelta(days=60)
        apply_event(self.db, _sub_event(
            event="subscription_updated", renews_at=_iso(later),
            updated=NOW + timedelta(days=30)))
        sub = self.db.scalar(select(Subscription))
        end = sub.current_period_end.replace(tzinfo=timezone.utc)
        self.assertEqual(end, later)

    def test_plan_change_in_portal_follows(self):
        apply_event(self.db, _sub_event())
        apply_event(self.db, _sub_event(
            event="subscription_updated", plan="desk", updated=NOW + timedelta(minutes=1)))
        self.assertEqual(self.db.scalar(select(Subscription)).plan_code, "desk")

    def test_unknown_plan_is_reported_not_retried(self):
        out = apply_event(self.db, _sub_event(plan="gold"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "unknown_plan")
        self.assertIsNone(self.db.scalar(select(Subscription)))

    def test_admin_account_is_never_touched(self):
        self.db.add(User(username="admin", password_hash="x", role="admin", email="buyer@example.com"))
        self.db.commit()
        out = apply_event(self.db, _sub_event())
        self.assertEqual(out["reason"], "admin_account")
        self.assertIsNone(self.db.scalar(select(Subscription)))

    def test_auto_renewing_subscription_has_no_due_reminder(self):
        apply_event(self.db, _sub_event(renews_at=_iso(NOW + timedelta(days=2))))
        user = self.db.scalar(select(User))
        view = subscription_view(self.db, user)
        self.assertTrue(view["auto_renew"])
        self.assertEqual(view["notice"], "none")
        self.assertIn("/de/pricing", view["pay_url"])
        self.assertEqual(view["manage_url"], "https://fxnavigator.net/de/billing?token=abc")

    def test_past_due_pays_again_through_the_site(self):
        # карту у maib не сменить: «Оплатить» ведёт на тарифы, не на страницу подписки
        apply_event(self.db, _sub_event(renews_at=_iso(NOW - timedelta(days=1))))
        apply_event(self.db, _sub_event(
            "past_due", event="subscription_updated", updated=NOW + timedelta(minutes=1)))
        view = subscription_view(self.db, self.db.scalar(select(User)))
        self.assertEqual(view["notice"], "past_due")
        self.assertIn("/de/pricing", view["pay_url"])

    def test_refund_expiry_ends_access_now(self):
        apply_event(self.db, _sub_event())
        apply_event(self.db, _sub_event(
            "expired", event="subscription_expired", ends_at=_iso(NOW),
            updated=NOW + timedelta(minutes=1)))
        sub = self.db.scalar(select(Subscription))
        self.assertEqual(effective_status(sub, NOW + timedelta(minutes=2)), "cancelled")


class PaymentEventTest(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        patcher = mock.patch.object(provider, "send_email", return_value=True)
        self.send_email = patcher.start()
        self.addCleanup(patcher.stop)
        apply_event(self.db, _sub_event())
        self.send_email.reset_mock()  # приветственное письмо нового аккаунта

    def test_payment_is_recorded_once(self):
        apply_event(self.db, _pay_event())
        apply_event(self.db, _pay_event())
        rows = self.db.scalars(select(Payment)).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].amount_cents, 4900)
        self.assertEqual(rows[0].currency, "EUR")
        self.assertEqual(rows[0].source, "maib")
        self.assertEqual(rows[0].plan_code, "pro")
        self.assertEqual(rows[0].status, "paid")
        self.assertEqual(rows[0].invoice_no, "C0FFEE00")

    def test_receipt_has_what_maib_requires_and_is_sent_once(self):
        apply_event(self.db, _pay_event())
        apply_event(self.db, _pay_event())  # повтор из outbox витрины
        self.send_email.assert_called_once()
        _, to, subject, body = self.send_email.call_args.args
        self.assertEqual(to, "buyer@example.com")
        self.assertIn("C0FFEE00", subject)
        # номер заказа, продавец, описание, сумма, валюта, дата
        for part in ("C0FFEE00", "IGBFXNavigator S.R.L.", "IDNO 1026023163277",
                     "FX Navigator Premium, 1 month", "49.00 EUR", NOW.strftime("%Y-%m-%d"),
                     "510218******1124", "https://fxnavigator.net/de/billing?token=abc"):
            self.assertIn(part, body)

    def test_test_payment_receipt_says_so(self):
        apply_event(self.db, _pay_event(test_mode=True))
        body = self.send_email.call_args.args[3]
        self.assertTrue(body.startswith("TESTZAHLUNG"))  # язык покупателя — de

    def test_failed_renewal_mails_once_with_retry_date(self):
        retry = NOW + timedelta(days=2)
        ev = dict(object_id="c0ffee00-0000-4000-8000-000000005599", order_no="C0FFEE99",
                  status="failed", billing_reason="renewal", status_message="Insufficient funds",
                  next_charge_at=_iso(retry))
        apply_event(self.db, _pay_event("subscription_payment_failed", **ev))
        apply_event(self.db, _pay_event("subscription_payment_failed", **ev))
        self.send_email.assert_called_once()
        body = self.send_email.call_args.args[3]
        self.assertIn("Insufficient funds", body)
        self.assertIn(retry.strftime("%Y-%m-%d"), body)
        self.assertIn("/de/pricing", body)

    def test_full_refund_marks_refunded_partial_keeps_net(self):
        apply_event(self.db, _pay_event())
        apply_event(self.db, _pay_event("subscription_payment_refunded",
                                        status="partial_refund", refunded_cents=900))
        pay = self.db.scalar(select(Payment))
        self.assertEqual(pay.status, "paid")
        self.assertEqual(pay.amount_cents, 4000)

        apply_event(self.db, _pay_event("subscription_payment_refunded",
                                        status="refunded", refunded_cents=4900))
        self.assertEqual(pay.status, "refunded")

    def test_failure_after_success_does_not_unpay(self):
        apply_event(self.db, _pay_event())
        out = apply_event(self.db, _pay_event("subscription_payment_failed", status="pending"))
        self.assertEqual(out.get("kept"), "paid")
        self.assertEqual(self.db.scalar(select(Payment)).status, "paid")

    def test_zero_invoice_is_not_a_payment(self):
        apply_event(self.db, _pay_event(object_id="c0ffee00-0000-4000-8000-000000005502",
                                        order_no="C0FFEE02", amount_cents=0))
        self.assertIsNone(self.db.scalar(select(Payment).where(Payment.invoice_no == "C0FFEE02")))


class AccountLinkTest(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        for name, value in (("BILLING_WEBHOOK_SECRET", "s3cret"),):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(provider, "send_email", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_token_round_trip_and_tamper(self):
        token = account_token(42)
        self.assertEqual(verify_account(token), 42)
        self.assertIsNone(verify_account("43." + token.split(".")[1]))
        self.assertIsNone(verify_account("garbage"))

    def test_signed_account_wins_over_a_different_checkout_email(self):
        user = User(username="trader", password_hash="x", role="user", email="")
        self.db.add(user)
        self.db.commit()
        out = apply_event(self.db, _sub_event(email="other@example.com", account=account_token(user.id)))
        self.assertEqual(out["user_id"], user.id)
        self.assertFalse(out["created"])
        self.assertEqual(len(self.db.scalars(select(User)).all()), 1)


if __name__ == "__main__":
    unittest.main()
