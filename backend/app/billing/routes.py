"""Подписка глазами пользователя и администратора.

Два роутера:

- `/api/billing/*` — то, что человек видит про себя: тариф, срок, права,
  история оплат, список тарифов для перехода.
- `/api/admin/billing/*` и `/api/admin/users/*` — панель администратора:
  кто заплатил, кто нет, сколько осталось, и всё, что можно сделать с
  аккаунтом, не трогая базу руками.

Каждый административный маршрут закрыт `require_admin` на сервере. Спрятанная
из меню кнопка — не защита.

Ни один ответ не содержит пароля брокера или ключа API: только признак, задан
он или нет.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import audit, current_user, get_db, require_admin
from ..auth.security import hash_password
from ..i18n import t
from ..models import (
    AuditLog,
    CustomerProfile,
    AuthToken,
    Payment,
    Plan,
    Signal,
    Subscription,
    User,
    UserEvent,
    utcnow,
)
from .health import customer_health, health_band
from .plans import ENTITLEMENT_KEYS, merged_entitlements
from .service import (
    ACTIVE_STATES,
    days_left,
    effective_status,
    extend,
    get_subscription,
    start_subscription,
    subscription_view,
)

billing_router = APIRouter(prefix="/api/billing")
admin_billing_router = APIRouter(prefix="/api/admin")


# --------------------------------------------------------------------------
# Пользователь о себе
# --------------------------------------------------------------------------


@billing_router.get("/me")
def my_subscription(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Тариф, срок, права и что показать поверх интерфейса."""
    return subscription_view(db, user)


@billing_router.get("/plans")
def list_plans(db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Тарифы, доступные для перехода (выключенные не показываем)."""
    rows = db.scalars(select(Plan).where(Plan.active == 1).order_by(Plan.sort)).all()
    return [
        {
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "price_cents": p.price_cents,
            "currency": p.currency,
            "period_days": p.period_days,
            "entitlements": merged_entitlements(p.entitlements),
        }
        for p in rows
    ]


@billing_router.get("/payments")
def my_payments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """История оплат — то, что человек вправе показать бухгалтеру."""
    rows = db.scalars(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
    ).all()
    return [_payment_out(p) for p in rows]


# --------------------------------------------------------------------------
# Администратор: обзор
# --------------------------------------------------------------------------


@admin_billing_router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Одна сводка на вопрос «всё ли в порядке прямо сейчас».

    Деньги считаются по фактическим оплатам, а не по тарифам подписок:
    скидка, ручной перевод и возврат иначе не сходятся с выпиской.
    """
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    users = db.scalars(select(User)).all()
    subs = {s.user_id: s for s in db.scalars(select(Subscription)).all()}

    by_status: dict[str, int] = {}
    by_plan: dict[str, int] = {}
    due_soon = 0
    for u in users:
        sub = subs.get(u.id)
        status = effective_status(sub)
        by_status[status] = by_status.get(status, 0) + 1
        if sub and status in ACTIVE_STATES:
            by_plan[sub.plan_code] = by_plan.get(sub.plan_code, 0) + 1
            left = days_left(sub)
            if left is not None and 0 <= left <= 7:
                due_soon += 1

    paid_month = db.scalar(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.status == "paid", Payment.created_at >= month_start
        )
    )
    mrr = db.scalar(
        select(func.coalesce(func.sum(Plan.price_cents), 0))
        .select_from(Subscription)
        .join(Plan, Plan.code == Subscription.plan_code)
        .where(Subscription.status.in_(("active", "past_due")))
    )

    day_ago = now - timedelta(days=1)
    return {
        "users_total": len(users),
        "users_new_24h": sum(
            1 for u in users if u.created_at and _aware(u.created_at) >= day_ago
        ),
        "subscriptions_by_status": by_status,
        "subscriptions_by_plan": by_plan,
        "due_in_7_days": due_soon,
        "revenue_month_cents": int(paid_month or 0),
        "mrr_cents": int(mrr or 0),
        "signals_open": db.scalar(
            select(func.count()).select_from(Signal).where(Signal.status == "open")
        )
        or 0,
        "signals_24h": db.scalar(
            select(func.count()).select_from(Signal).where(Signal.created_at >= day_ago)
        )
        or 0,
        "events_24h": db.scalar(
            select(func.count()).select_from(UserEvent).where(UserEvent.created_at >= day_ago)
        )
        or 0,
        "measured_at": now.isoformat(),
    }


@admin_billing_router.get("/billing/subscriptions")
def admin_subscriptions(
    view: str = "all",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Кто заплатил, кто нет и сколько осталось.

    `view`: all | due_soon | past_due | suspended | trialing — те вопросы, на
    которые администратор отвечает каждый день, без запроса руками.
    """
    users = {u.id: u for u in db.scalars(select(User)).all()}
    plans = {p.code: p for p in db.scalars(select(Plan)).all()}
    rows = []
    for sub in db.scalars(select(Subscription).order_by(Subscription.current_period_end)).all():
        user = users.get(sub.user_id)
        if user is None:
            continue
        status = effective_status(sub)
        left = days_left(sub)
        if view == "due_soon" and not (status in ACTIVE_STATES and left is not None and 0 <= left <= 7):
            continue
        if view in ("past_due", "suspended", "trialing") and status != view:
            continue
        plan = plans.get(sub.plan_code)
        rows.append(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email or "",
                "plan_code": sub.plan_code,
                "plan_name": plan.name if plan else sub.plan_code,
                "price_cents": plan.price_cents if plan else 0,
                "status": status,
                "trial": bool(sub.trial),
                "current_period_end": sub.current_period_end.isoformat()
                if sub.current_period_end
                else None,
                "days_left": left,
                "cancel_at_period_end": bool(sub.cancel_at_period_end),
                "note": sub.note,
            }
        )
    return rows


@admin_billing_router.get("/customers")
def customers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Клиенты с оценкой здоровья, метками и следующим шагом.

    Оценка считается здесь, а не хранится: она зависит от «сколько дней назад»,
    то есть меняется сама по себе. Сохранённое значение устаревало бы молча.
    """
    now = utcnow()
    month_ago = now - timedelta(days=30)

    subs = {s.user_id: s for s in db.scalars(select(Subscription)).all()}
    plans = {p.code: p for p in db.scalars(select(Plan)).all()}
    profiles = {p.user_id: p for p in db.scalars(select(CustomerProfile)).all()}

    pay_counts: dict[int, int] = {}
    for uid, in db.execute(select(Payment.user_id).where(Payment.status == "paid")).all():
        pay_counts[uid] = pay_counts.get(uid, 0) + 1

    last_seen: dict[int, datetime] = {}
    events_30d: dict[int, int] = {}
    for uid, kind, created in db.execute(
        select(UserEvent.user_id, UserEvent.kind, UserEvent.created_at)
    ).all():
        when = _aware(created)
        if kind == "login" and (uid not in last_seen or when > last_seen[uid]):
            last_seen[uid] = when
        if when >= month_ago:
            events_30d[uid] = events_30d.get(uid, 0) + 1

    rows = []
    for user in db.scalars(select(User).order_by(User.created_at)).all():
        sub = subs.get(user.id)
        status = effective_status(sub)
        plan = plans.get(sub.plan_code) if sub else None
        profile = profiles.get(user.id)
        health = customer_health(
            status=status,
            days_left=days_left(sub),
            last_seen=last_seen.get(user.id),
            payments=pay_counts.get(user.id, 0),
            events_30d=events_30d.get(user.id, 0),
            now=now,
        )
        rows.append(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email or "",
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "plan_code": sub.plan_code if sub else "",
                "plan_name": plan.name if plan else "",
                "price_cents": plan.price_cents if plan else 0,
                "status": status,
                "days_left": days_left(sub),
                "current_period_end": sub.current_period_end.isoformat()
                if sub and sub.current_period_end
                else None,
                "last_seen": last_seen[user.id].isoformat() if user.id in last_seen else None,
                "payments": pay_counts.get(user.id, 0),
                "events_30d": events_30d.get(user.id, 0),
                "health": health["score"],
                "health_band": health_band(health["score"]),
                "health_factors": health["factors"],
                "tags": list(profile.tags or []) if profile else [],
                "note": profile.note if profile else "",
                "next_action": profile.next_action if profile else "",
                "next_action_due": profile.next_action_due.isoformat()
                if profile and profile.next_action_due
                else None,
                "urgent": bool(profile.urgent) if profile else False,
            }
        )

    # срочные наверх, потом самые слабые по здоровью
    rows.sort(key=lambda r: (not r["urgent"], r["health"]))
    return rows


class ProfileInput(BaseModel):
    tags: list[str] | None = None
    note: str | None = None
    next_action: str | None = None
    next_action_due: str | None = None
    urgent: bool | None = None


@admin_billing_router.put("/customers/{user_id}/profile")
def save_profile(
    user_id: int,
    req: ProfileInput,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Метки, заметка и следующий шаг по клиенту."""
    if db.get(User, user_id) is None:
        raise HTTPException(404, t("пользователь не найден"))

    profile = db.get(CustomerProfile, user_id)
    if profile is None:
        profile = CustomerProfile(user_id=user_id)
        db.add(profile)

    if req.tags is not None:
        profile.tags = [tag.strip()[:32] for tag in req.tags if tag.strip()][:12]
    if req.note is not None:
        profile.note = req.note[:4000]
    if req.next_action is not None:
        profile.next_action = req.next_action[:256]
    if req.next_action_due is not None:
        try:
            profile.next_action_due = (
                datetime.fromisoformat(req.next_action_due) if req.next_action_due else None
            )
        except ValueError:
            raise HTTPException(400, t("дата в неверном формате")) from None
    if req.urgent is not None:
        profile.urgent = 1 if req.urgent else 0

    profile.updated_by = admin.username
    profile.updated_at = utcnow()
    db.commit()
    audit(db, request, admin, "customer_profile_saved", f"user {user_id}")
    return {"ok": True}


@admin_billing_router.get("/billing/payments")
def admin_payments(
    limit: int = 200, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    """Последние оплаты по всем пользователям."""
    users = {u.id: u.username for u in db.scalars(select(User)).all()}
    rows = db.scalars(
        select(Payment).order_by(Payment.created_at.desc()).limit(min(limit, 1000))
    ).all()
    return [{**_payment_out(p), "username": users.get(p.user_id, "")} for p in rows]


@admin_billing_router.get("/charts")
def admin_charts(days: int = 30, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Ряды для графиков: регистрации, оплаты, сигналы, активность.

    Считается по дням в UTC. Дни без событий присутствуют с нулём — иначе
    график рисует прямую между далёкими точками и врёт о провале.
    """
    span = max(1, min(days, 365))
    start = (utcnow() - timedelta(days=span)).replace(hour=0, minute=0, second=0, microsecond=0)
    keys = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(span + 1)]

    def bucket(rows: list[datetime]) -> dict[str, int]:
        out = {k: 0 for k in keys}
        for value in rows:
            key = _aware(value).strftime("%Y-%m-%d")
            if key in out:
                out[key] += 1
        return out

    signups = bucket(
        list(db.scalars(select(User.created_at).where(User.created_at >= start)).all())
    )
    signals = bucket(
        list(db.scalars(select(Signal.created_at).where(Signal.created_at >= start)).all())
    )
    events = bucket(
        list(db.scalars(select(UserEvent.created_at).where(UserEvent.created_at >= start)).all())
    )

    revenue = {k: 0 for k in keys}
    for created_at, amount in db.execute(
        select(Payment.created_at, Payment.amount_cents).where(
            Payment.status == "paid", Payment.created_at >= start
        )
    ).all():
        key = _aware(created_at).strftime("%Y-%m-%d")
        if key in revenue:
            revenue[key] += int(amount or 0)

    return {
        "days": keys,
        "signups": [signups[k] for k in keys],
        "signals": [signals[k] for k in keys],
        "events": [events[k] for k in keys],
        "revenue_cents": [revenue[k] for k in keys],
    }


# --------------------------------------------------------------------------
# Администратор: один пользователь
# --------------------------------------------------------------------------


@admin_billing_router.get("/users/{user_id}/detail")
def user_detail(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Всё об одном аккаунте на одной странице.

    Credentials не возвращаются никогда — только признак, что они заданы.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, t("пользователь не найден"))

    sub = get_subscription(db, user_id)
    plan = db.get(Plan, sub.plan_code) if sub else None
    sessions = db.scalar(
        select(func.count()).select_from(AuthToken).where(AuthToken.user_id == user_id)
    )

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email or "",
            "role": user.role,
            "language": user.language or "ru",
            "totp_enabled": bool(user.totp_enabled),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "has_recovery_email": bool(user.email),
            "active_sessions": int(sessions or 0),
        },
        "subscription": None
        if sub is None
        else {
            "plan_code": sub.plan_code,
            "plan_name": plan.name if plan else sub.plan_code,
            "status": effective_status(sub),
            "trial": bool(sub.trial),
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "current_period_end": sub.current_period_end.isoformat()
            if sub.current_period_end
            else None,
            "days_left": days_left(sub),
            "grace_days": sub.grace_days,
            "cancel_at_period_end": bool(sub.cancel_at_period_end),
            "note": sub.note,
        },
        "payments": [
            _payment_out(p)
            for p in db.scalars(
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc())
                .limit(50)
            ).all()
        ],
        "events": [
            {
                "id": e.id,
                "kind": e.kind,
                "detail": e.detail,
                "ip": e.ip,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in db.scalars(
                select(UserEvent)
                .where(UserEvent.user_id == user_id)
                .order_by(UserEvent.created_at.desc())
                .limit(100)
            ).all()
        ],
        "signals_total": db.scalar(
            select(func.count()).select_from(Signal)
        )
        or 0,
    }


class PlanChange(BaseModel):
    plan_code: str
    days: int | None = None
    trial: bool = False
    note: str = ""


@admin_billing_router.post("/users/{user_id}/subscription")
def set_subscription(
    user_id: int,
    req: PlanChange,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Назначить тариф. Заменяет текущую подписку новой."""
    if db.get(User, user_id) is None:
        raise HTTPException(404, t("пользователь не найден"))
    try:
        sub = start_subscription(
            db, user_id, req.plan_code, trial=req.trial, days=req.days, note=req.note
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    audit(db, request, admin, "subscription_set", f"user {user_id} -> {req.plan_code}")
    return {"ok": True, "status": effective_status(sub)}


class ExtendRequest(BaseModel):
    days: int


@admin_billing_router.post("/users/{user_id}/subscription/extend")
def extend_subscription(
    user_id: int,
    req: ExtendRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Продлить (или сократить отрицательным числом) период."""
    sub = get_subscription(db, user_id)
    if sub is None:
        raise HTTPException(404, t("подписка не найдена"))
    extend(db, sub, req.days)
    audit(db, request, admin, "subscription_extended", f"user {user_id} {req.days:+d}d")
    return {"ok": True, "current_period_end": sub.current_period_end.isoformat()}


class SubscriptionState(BaseModel):
    status: str


@admin_billing_router.post("/users/{user_id}/subscription/status")
def set_subscription_status(
    user_id: int,
    req: SubscriptionState,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Приостановить, отменить или вернуть подписку вручную."""
    allowed = ("active", "suspended", "cancelled")
    if req.status not in allowed:
        raise HTTPException(400, t("состояние: {0}", ", ".join(allowed)))
    sub = get_subscription(db, user_id)
    if sub is None:
        raise HTTPException(404, t("подписка не найдена"))
    sub.status = req.status
    sub.updated_at = utcnow()
    db.commit()
    audit(db, request, admin, "subscription_status", f"user {user_id} -> {req.status}")
    return {"ok": True, "status": effective_status(sub)}


class ManualPayment(BaseModel):
    amount_cents: int
    currency: str = "EUR"
    plan_code: str = ""
    extend_days: int | None = None
    note: str = ""


@admin_billing_router.post("/users/{user_id}/payments")
def record_payment(
    user_id: int,
    req: ManualPayment,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Отметить оплату вручную — банковский перевод, наличные, зачёт.

    Отдельно от продления: администратор может отметить деньги, не трогая
    срок, и наоборот.
    """
    if db.get(User, user_id) is None:
        raise HTTPException(404, t("пользователь не найден"))
    payment = Payment(
        user_id=user_id,
        plan_code=req.plan_code,
        amount_cents=req.amount_cents,
        currency=req.currency,
        status="paid",
        source="manual",
        note=req.note,
        invoice_no=f"INV-{utcnow():%Y%m}-{user_id}-{int(utcnow().timestamp()) % 100000}",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    if req.extend_days:
        sub = get_subscription(db, user_id)
        if sub is not None:
            extend(db, sub, req.extend_days)

    audit(
        db, request, admin, "payment_recorded",
        f"user {user_id} {req.amount_cents / 100:.2f} {req.currency}",
    )
    return _payment_out(payment)


class PasswordReset(BaseModel):
    password: str


@admin_billing_router.post("/users/{user_id}/password")
def admin_set_password(
    user_id: int,
    req: PasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Назначить пользователю новый пароль и разлогинить его везде."""
    if len(req.password) < 8:
        raise HTTPException(400, t("пароль не короче 8 символов"))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, t("пользователь не найден"))
    user.password_hash = hash_password(req.password)
    for token in db.scalars(select(AuthToken).where(AuthToken.user_id == user_id)).all():
        db.delete(token)
    db.commit()
    audit(db, request, admin, "password_reset_by_admin", user.username)
    return {"ok": True}


@admin_billing_router.post("/users/{user_id}/logout-all")
def logout_everywhere(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Завершить все сессии пользователя."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, t("пользователь не найден"))
    count = 0
    for token in db.scalars(select(AuthToken).where(AuthToken.user_id == user_id)).all():
        db.delete(token)
        count += 1
    db.commit()
    audit(db, request, admin, "sessions_revoked", f"{user.username} ({count})")
    return {"ok": True, "revoked": count}


@admin_billing_router.get("/events")
def all_events(
    limit: int = 300,
    user_id: int | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Активность пользователей, с фильтрами по человеку и типу."""
    users = {u.id: u.username for u in db.scalars(select(User)).all()}
    query = select(UserEvent).order_by(UserEvent.created_at.desc())
    if user_id is not None:
        query = query.where(UserEvent.user_id == user_id)
    if kind:
        query = query.where(UserEvent.kind == kind)
    rows = db.scalars(query.limit(min(limit, 2000))).all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "username": users.get(e.user_id, ""),
            "kind": e.kind,
            "detail": e.detail,
            "ip": e.ip,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


# --------------------------------------------------------------------------
# Администратор: тарифы
# --------------------------------------------------------------------------


class PlanInput(BaseModel):
    code: str
    name: str
    description: str = ""
    price_cents: int = 0
    currency: str = "EUR"
    period_days: int = 30
    entitlements: dict[str, Any] = {}
    active: bool = True
    sort: int = 0


@admin_billing_router.get("/plans")
def admin_plans(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Все тарифы, включая выключенные, с полным набором прав."""
    rows = db.scalars(select(Plan).order_by(Plan.sort)).all()
    return {
        "plans": [
            {
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "price_cents": p.price_cents,
                "currency": p.currency,
                "period_days": p.period_days,
                "entitlements": merged_entitlements(p.entitlements),
                "active": bool(p.active),
                "sort": p.sort,
            }
            for p in rows
        ],
        # ключи прав с пояснениями — админке не нужно знать их наизусть
        "entitlement_keys": ENTITLEMENT_KEYS,
    }


@admin_billing_router.put("/plans/{code}")
def upsert_plan(
    code: str,
    req: PlanInput,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Завести или изменить тариф — без выката."""
    plan = db.get(Plan, code)
    if plan is None:
        plan = Plan(code=code)
        db.add(plan)
    plan.name = req.name
    plan.description = req.description
    plan.price_cents = req.price_cents
    plan.currency = req.currency
    plan.period_days = req.period_days
    plan.entitlements = {k: v for k, v in req.entitlements.items() if k in ENTITLEMENT_KEYS}
    plan.active = 1 if req.active else 0
    plan.sort = req.sort
    db.commit()
    audit(db, request, admin, "plan_saved", code)
    return {"ok": True}


# --------------------------------------------------------------------------
# Вспомогательное
# --------------------------------------------------------------------------


def _payment_out(p: Payment) -> dict[str, Any]:
    """Оплата для выдачи наружу."""
    return {
        "id": p.id,
        "user_id": p.user_id,
        "plan_code": p.plan_code,
        "amount_cents": p.amount_cents,
        "currency": p.currency,
        "status": p.status,
        "source": p.source,
        "invoice_no": p.invoice_no,
        "note": p.note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _aware(value: datetime) -> datetime:
    """Время из SQLite — naive; сравнивать с UTC-aware без этого нельзя."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
