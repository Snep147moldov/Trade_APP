"""Id удалённого аккаунта не достаётся новому, удаление не оставляет доступа.

25.11.2026 аккаунт maib-test@ получил id 3 вместе с двумя пробными подписками,
событиями и журналом двух удалённых аккаунтов: SQLite без AUTOINCREMENT
переиспользует id последней удалённой строки, а удаление чистило только сессии.
Будь у удалённого оплаченная подписка, новый аккаунт получил бы её даром.
"""

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex, CreateTable

from app.auth.accounts import delete_account, renewing_subscription
from app.auth.routes import ResetRequest, delete_user, reset_password
from app.auth.security import hash_password, verify_password
from app.billing.service import get_subscription, seed_plans
from app.database import Base, _never_reuse_user_ids
from app.models import (AuditLog, AuthToken, CustomerProfile, Payment, Subscription, User,
                        UserEvent)

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return eng


def _make_old_style(eng) -> None:
    """users как в старых базах: INTEGER PRIMARY KEY без AUTOINCREMENT."""
    ddl = str(CreateTable(User.__table__).compile(dialect=eng.dialect))
    assert "AUTOINCREMENT" in ddl
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE users"))
        conn.execute(text(ddl.replace(" AUTOINCREMENT", "")))
        for index in User.__table__.indexes:
            conn.execute(text(str(CreateIndex(index).compile(dialect=eng.dialect))))


def _user(db, name, at, role="user") -> User:
    u = User(username=name, password_hash="x", role=role, email=f"{name}@example.com",
             created_at=at)
    db.add(u)
    db.commit()
    return u


def _ddl(eng) -> str:
    with eng.connect() as conn:
        return conn.execute(text("SELECT sql FROM sqlite_master WHERE name='users'")).scalar()


class FreshInstallTest(unittest.TestCase):
    def test_deleted_last_id_is_not_reused(self):
        eng = _engine()
        self.assertIn("AUTOINCREMENT", _ddl(eng).upper())
        db = Session(eng)
        _user(db, "a", T0)
        b = _user(db, "b", T0)
        db.delete(b)
        db.commit()
        self.assertEqual(_user(db, "c", T0).id, 3)
        self.assertIsNone(_never_reuse_user_ids(eng))  # уже правильная таблица


class OldDatabaseMigrationTest(unittest.TestCase):
    def setUp(self):
        self.eng = _engine()
        _make_old_style(self.eng)
        self.db = Session(self.eng)
        seed_plans(self.db)

    def test_old_table_reuses_ids_and_migration_stops_it(self):
        db = self.db
        _user(db, "admin", T0, role="admin")
        gone = _user(db, "gone", T0)
        db.add_all([
            Subscription(user_id=gone.id, plan_code="pro", status="active",
                         current_period_end=T0 + timedelta(days=365), created_at=T0 + timedelta(days=1)),
            UserEvent(user_id=gone.id, kind="login", created_at=T0 + timedelta(days=1)),
            AuditLog(user_id=gone.id, username="gone", action="login_ok", created_at=T0 + timedelta(days=1)),
            # аккаунт с большим id, удалённый ещё раньше: от него осталась только оплата
            Payment(user_id=7, plan_code="pro", amount_cents=100, created_at=T0),
        ])
        db.commit()
        db.delete(gone)
        db.commit()

        # так было в проде: новый аккаунт получает id удалённого и его подписку
        heir = _user(db, "heir", T0 + timedelta(days=2))
        self.assertEqual(heir.id, 2)
        self.assertEqual(get_subscription(db, heir.id).plan_code, "pro")
        own = Subscription(user_id=heir.id, plan_code="trial", status="trialing",
                           current_period_end=T0 + timedelta(days=9), created_at=T0 + timedelta(days=3))
        db.add(own)
        db.commit()
        db.close()

        detached = _never_reuse_user_ids(self.eng)
        self.assertEqual(detached, {"subscriptions": 1, "user_events": 1, "audit_log": 1})
        self.assertIn("AUTOINCREMENT", _ddl(self.eng).upper())

        db = Session(self.eng)
        # строки пережили пересборку, со всеми колонками
        heir = db.get(User, 2)
        self.assertEqual((heir.username, heir.email), ("heir", "heir@example.com"))
        # своё осталось, унаследованное ушло
        subs = db.scalars(select(Subscription).where(Subscription.user_id == 2)).all()
        self.assertEqual([s.plan_code for s in subs], ["trial"])
        self.assertIsNone(db.scalar(select(AuditLog).where(AuditLog.user_id == 2)))
        self.assertEqual(db.scalar(select(AuditLog)).username, "gone")  # след остался
        # следующий id — выше любого, на который ещё ссылаются строки (оплата id 7)
        self.assertEqual(_user(db, "next", T0 + timedelta(days=4)).id, 8)
        # повторный запуск ничего не делает
        self.assertIsNone(_never_reuse_user_ids(self.eng))


class DeleteAccountTest(unittest.TestCase):
    def setUp(self):
        self.db = Session(_engine())
        seed_plans(self.db)
        self.admin = _user(self.db, "admin", T0, role="admin")
        self.user = _user(self.db, "buyer", T0)

    def _fill(self, provider="", cancelled=0):
        now = datetime.now(timezone.utc)
        self.db.add_all([
            AuthToken(token="tok", user_id=self.user.id, expires_at=now + timedelta(days=1)),
            Subscription(user_id=self.user.id, plan_code="pro", status="active", provider=provider,
                         cancel_at_period_end=cancelled, current_period_end=now + timedelta(days=30)),
            UserEvent(user_id=self.user.id, kind="login"),
            CustomerProfile(user_id=self.user.id, note="позвонить"),
            Payment(user_id=self.user.id, plan_code="pro", amount_cents=9900, note="первая оплата"),
        ])
        self.db.commit()

    def test_access_goes_money_stays(self):
        self._fill()
        uid = self.user.id
        removed = delete_account(self.db, self.user)
        self.assertEqual(removed["subscriptions"], 1)
        self.assertEqual(removed["payments_kept"], 1)
        for model in (AuthToken, Subscription, UserEvent, CustomerProfile):
            self.assertIsNone(self.db.scalar(select(model).where(model.user_id == uid)), model)
        pay = self.db.scalar(select(Payment))
        self.assertEqual(pay.note, "первая оплата; аккаунт buyer удалён")
        self.assertEqual(_user(self.db, "new", T0).id, uid + 1)

    def test_route_refuses_while_card_still_renews(self):
        self._fill(provider="maib")
        self.assertIsNotNone(renewing_subscription(self.db, self.user))
        with self.assertRaises(HTTPException) as err:
            delete_user(self.user.id, None, self.db, self.admin)
        self.assertEqual(err.exception.status_code, 409)
        self.assertIsNotNone(self.db.get(User, self.user.id))

    def test_route_deletes_after_auto_renewal_cancelled(self):
        self._fill(provider="maib", cancelled=1)
        self.assertIsNone(renewing_subscription(self.db, self.user))
        out = delete_user(self.user.id, None, self.db, self.admin)
        self.assertTrue(out["ok"])
        self.assertIsNone(self.db.get(User, self.user.id))

    def test_route_refuses_own_account_with_a_message(self):
        # раньше: UnboundLocalError (локальная `t` в цикле затеняла перевод) -> 500
        with self.assertRaises(HTTPException) as err:
            delete_user(self.admin.id, None, self.db, self.admin)
        self.assertEqual(err.exception.status_code, 400)


class ResetPasswordTest(unittest.TestCase):
    """Сброс по коду — вход для каждого, кто купил без аккаунта. Падал с 500 всегда."""

    def setUp(self):
        self.db = Session(_engine())
        self.user = _user(self.db, "buyer@example.com", T0)
        self.user.reset_hash = hash_password("123456")
        self.user.reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        self.db.add(AuthToken(token="old", user_id=self.user.id,
                              expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        self.db.commit()

    def test_valid_code_sets_password_and_ends_sessions(self):
        out = reset_password(ResetRequest(username="buyer@example.com", code="123456",
                                          new_password="new-password-1"), None, self.db)
        self.assertTrue(out["ok"])
        self.assertTrue(verify_password("new-password-1", self.user.password_hash))
        self.assertIsNone(self.db.get(AuthToken, "old"))

    def test_short_password_and_wrong_code_are_400_not_500(self):
        for req in (ResetRequest(username="buyer@example.com", code="123456", new_password="short"),
                    ResetRequest(username="buyer@example.com", code="000000", new_password="long-enough-1")):
            with self.assertRaises(HTTPException) as err:
                reset_password(req, None, self.db)
            self.assertEqual(err.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
