"""Состояние подписки и проверка прав.

Единственное место, которое отвечает на вопрос «что этому человеку сейчас
можно». Экраны, API и планировщик спрашивают здесь и нигде больше — иначе две
проверки расходятся, и пользователь видит «активна» на одной странице и
«истекла» на другой.

Состояния и переходы:

    trialing ──оплата──> active ──конец периода──> past_due
       │                   │                          │
       └──конец периода────┘                   льготные дни вышли
                           │                          ↓
                      cancelled ──конец периода──> suspended
                                                      │
                                                   оплата
                                                      ↓
                                                   active

`suspended` — не «нельзя войти». Историю человек видит: он за неё заплатил.
Нельзя создавать новое и нельзя торговать.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Plan, Subscription, User, utcnow
from .plans import DEFAULT_PLANS, allows, merged_entitlements

#: Состояния, при которых доступ к функциям продукта открыт.
ACTIVE_STATES = ("trialing", "active", "past_due")

#: Состояния, при которых открыт только просмотр уже накопленного.
READ_ONLY_STATES = ("suspended", "expired", "cancelled")

#: За сколько дней до конца периода предупреждаем.
WARN_DAYS = (7, 3, 1)


class SubscriptionRequired(Exception):
    """Действие требует активной подписки.

    Отдельный тип, а не HTTPException: сервис не знает про HTTP, а слой API
    превращает это в 402 с понятным телом.
    """

    def __init__(self, reason: str, status: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class EntitlementDenied(Exception):
    """Тариф не включает это право или предел исчерпан."""

    def __init__(self, key: str, limit: Any) -> None:
        super().__init__(key)
        self.key = key
        self.limit = limit


def seed_plans(db: Session) -> int:
    """Завести тарифы по умолчанию, если их ещё нет.

    Существующие не трогает: администратор мог поменять цену или лимит, и
    перезапуск приложения не должен это откатывать.

    :param db: Сессия
    :returns: Сколько тарифов добавлено
    """
    added = 0
    for spec in DEFAULT_PLANS:
        if db.get(Plan, spec["code"]) is not None:
            continue
        db.add(Plan(**spec))
        added += 1
    if added:
        db.commit()
    return added


def backfill_subscriptions(db: Session, plan_code: str = "desk", days: int = 3650) -> int:
    """Выдать подписку тем, у кого её ещё нет.

    Нужно ровно один раз — при выкате подписок на установку, которая до этого
    про них не знала. Без этого владелец, заводивший систему для себя,
    оказывается заблокирован собственным платёжным экраном: подписки нет,
    значит `expired`, значит блок.

    Срок намеренно длинный, а тариф — старший: эти люди платили за установку,
    а не за доступ, и отбирать его переходом на подписочную модель нельзя.

    :param db: Сессия
    :param plan_code: Тариф, который выдать
    :param days: На сколько дней
    :returns: Сколько подписок заведено
    """
    if db.get(Plan, plan_code) is None:
        return 0
    existing = {s.user_id for s in db.scalars(select(Subscription)).all()}
    added = 0
    for user in db.scalars(select(User)).all():
        if user.id in existing:
            continue
        start_subscription(db, user.id, plan_code, days=days,
                           note="выдано при переходе на подписки")
        added += 1
    return added


def get_subscription(db: Session, user_id: int) -> Subscription | None:
    """Подписка пользователя (последняя заведённая).

    :param db: Сессия
    :param user_id: Пользователь
    :returns: Подписка или None
    """
    return db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def _as_utc(value: datetime | None) -> datetime | None:
    """Привести время из SQLite к UTC-aware.

    SQLite отдаёт naive datetime, и сравнение с `now(timezone.utc)` падает.

    :param value: Время из базы
    :returns: Время с зоной или None
    """
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def effective_status(sub: Subscription | None, now: datetime | None = None) -> str:
    """Состояние подписки на текущий момент.

    Считается из дат, а не берётся из колонки: иначе подписка, у которой период
    кончился ночью, до ближайшего запуска планировщика выглядела бы активной.
    Колонка `status` хранит решения, которые нельзя вывести из дат —
    отменена, приостановлена вручную.

    :param sub: Подписка
    :param now: Текущее время (для тестов)
    :returns: Одно из trialing | active | past_due | suspended | cancelled | expired
    """
    if sub is None:
        return "expired"
    moment = now or utcnow()
    if sub.status in ("suspended", "cancelled"):
        return sub.status

    period_end = _as_utc(sub.current_period_end)
    if period_end is None:
        return sub.status

    if moment <= period_end:
        return "trialing" if sub.trial else "active"

    grace_end = period_end + timedelta(days=max(0, sub.grace_days))
    if moment <= grace_end:
        return "past_due"
    return "suspended"


def days_left(sub: Subscription | None, now: datetime | None = None) -> int | None:
    """Сколько дней осталось до конца оплаченного периода.

    Отрицательное значение — период уже кончился и идут льготные дни.

    :param sub: Подписка
    :param now: Текущее время
    :returns: Дни или None, когда подписки нет
    """
    if sub is None:
        return None
    period_end = _as_utc(sub.current_period_end)
    if period_end is None:
        return None
    seconds = (period_end - (now or utcnow())).total_seconds()
    # вверх по модулю: «остался час» — это ещё день, а не ноль, и «час как
    # кончилось» — уже минус день, а не ноль
    days = int(abs(seconds) // 86400) + (1 if abs(seconds) % 86400 else 0)
    return days if seconds >= 0 else -days


def entitlements_for(db: Session, user: User) -> dict[str, Any]:
    """Права пользователя с учётом состояния подписки.

    Приостановленная подписка не оставляет прав на создание нового: числовые
    пределы обнуляются, логические выключаются. Просмотр истории правами не
    управляется и остаётся доступным.

    :param db: Сессия
    :param user: Пользователь
    :returns: Полный набор прав
    """
    sub = get_subscription(db, user.id)
    plan = db.get(Plan, sub.plan_code) if sub else None
    rights = merged_entitlements(plan.entitlements if plan else None)

    if effective_status(sub) not in ACTIVE_STATES:
        for key, value in list(rights.items()):
            if isinstance(value, bool):
                rights[key] = False
            elif isinstance(value, int):
                rights[key] = 0
    return rights


def assert_active(db: Session, user: User) -> Subscription:
    """Потребовать активную подписку.

    :param db: Сессия
    :param user: Пользователь
    :returns: Подписка
    :raises SubscriptionRequired: Когда подписки нет или она не активна
    """
    sub = get_subscription(db, user.id)
    status = effective_status(sub)
    if sub is None or status not in ACTIVE_STATES:
        raise SubscriptionRequired("подписка не активна", status)
    return sub


def assert_allows(db: Session, user: User, key: str, amount: int = 1) -> None:
    """Потребовать право.

    :param db: Сессия
    :param user: Пользователь
    :param key: Ключ права
    :param amount: Сколько единиц требуется
    :raises SubscriptionRequired: Подписка не активна
    :raises EntitlementDenied: Тариф не включает это право
    """
    assert_active(db, user)
    rights = entitlements_for(db, user)
    if not allows(rights, key, amount):
        raise EntitlementDenied(key, rights.get(key))


def start_subscription(
    db: Session,
    user_id: int,
    plan_code: str,
    *,
    trial: bool = False,
    days: int | None = None,
    note: str = "",
) -> Subscription:
    """Завести или заменить подписку пользователя.

    :param db: Сессия
    :param user_id: Пользователь
    :param plan_code: Код тарифа
    :param trial: Пробный период
    :param days: Длительность; по умолчанию — из тарифа
    :param note: Комментарий администратора
    :returns: Созданная подписка
    :raises ValueError: Неизвестный тариф
    """
    plan = db.get(Plan, plan_code)
    if plan is None:
        raise ValueError(f"неизвестный тариф {plan_code}")

    length = days if days is not None else plan.period_days
    sub = Subscription(
        user_id=user_id,
        plan_code=plan_code,
        status="trialing" if trial else "active",
        started_at=utcnow(),
        current_period_end=utcnow() + timedelta(days=length),
        trial=1 if trial else 0,
        note=note,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def extend(db: Session, sub: Subscription, days: int) -> Subscription:
    """Продлить период.

    Продление считается от конца текущего периода, а не от сегодня: иначе
    оплата, пришедшая за три дня до конца, съедала бы эти три дня.

    :param db: Сессия
    :param sub: Подписка
    :param days: На сколько дней
    :returns: Обновлённая подписка
    """
    base = max(_as_utc(sub.current_period_end) or utcnow(), utcnow())
    sub.current_period_end = base + timedelta(days=days)
    if sub.status in ("suspended", "expired"):
        sub.status = "active"
    sub.trial = 0
    sub.updated_at = utcnow()
    db.commit()
    db.refresh(sub)
    return sub


def subscription_view(db: Session, user: User) -> dict[str, Any]:
    """Что показать пользователю в настройках.

    :param db: Сессия
    :param user: Пользователь
    :returns: Тариф, состояние, сроки и права
    """
    sub = get_subscription(db, user.id)
    plan = db.get(Plan, sub.plan_code) if sub else None
    status = effective_status(sub)
    left = days_left(sub)

    return {
        "status": status,
        "active": status in ACTIVE_STATES,
        "read_only": status in READ_ONLY_STATES,
        "plan": None
        if plan is None
        else {
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "price_cents": plan.price_cents,
            "currency": plan.currency,
            "period_days": plan.period_days,
        },
        "trial": bool(sub.trial) if sub else False,
        "started_at": sub.started_at.isoformat() if sub and sub.started_at else None,
        "current_period_end": sub.current_period_end.isoformat()
        if sub and sub.current_period_end
        else None,
        "days_left": left,
        "grace_days": sub.grace_days if sub else 0,
        "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
        "entitlements": entitlements_for(db, user),
        # что показать поверх интерфейса: ничего, мягкое напоминание или блок
        "notice": _notice_level(status, left),
    }


def _notice_level(status: str, left: int | None) -> str:
    """Какое предупреждение показать поверх интерфейса.

    :param status: Состояние подписки
    :param left: Дней до конца периода
    :returns: none | due_soon | due | past_due | blocked
    """
    if status in READ_ONLY_STATES:
        return "blocked"
    if status == "past_due":
        return "past_due"
    if left is None:
        return "none"
    if left <= 0:
        return "due"
    if left <= max(WARN_DAYS):
        return "due_soon"
    return "none"
