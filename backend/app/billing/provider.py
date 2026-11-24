"""Оплаты картой через maib (BC «Moldova Agroindbank» SA).

Путь события::

    покупатель ──> витрина /api/checkout ──savecard-recurring──> страница оплаты maib
    maib ──callback, подпись Signature Key──> витрина /api/maib/callback
    витрина, cron ──execute-recurring──> maib      (продления, без участия покупателя)
    витрина ──короткое событие, X-Billing-Secret──> POST /api/hooks/billing

С банком говорит только витрина: у неё ключи проекта maib, сохранённые карты
(billerId) и график списаний (data/billing.db). Сюда событие приходит уже в
нашем виде, по внутренней сети docker, с общим секретом. Платформа заводит
аккаунт, двигает срок доступа и шлёт письма — в том числе подтверждение
оплаты, которое maib требует от магазина после каждого списания: у витрины
нет SMTP.

Правила, на которых всё держится:

- Срок и состояние доступа двигают только события подписки
  (`kind=subscription`): их `status`, `renews_at`, `ends_at` — правда о сроке.
  Оплаты (`kind=payment`) пишутся в историю и срок не трогают — иначе
  продление считалось бы дважды: от оплаты и от `subscription_updated`.
- Повтор безопасен. Подписка находится по id у провайдера, оплата — по
  `external_id`. Старое событие, пришедшее после нового (витрина повторяет
  неудачные доставки из outbox с растущей паузой), отбрасывается по `updated_at`.
- Покупатель без аккаунта получает аккаунт: логин — его e-mail, пароль он
  задаёт сам через «Забыли пароль?». Письмо с этим уходит сразу.
- Аккаунты администраторов провайдер не трогает: иначе любой, кто знает
  адрес администратора, купил и отменил бы подписку на него.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..auth.deps import audit, get_db
from ..auth.security import hash_password
from ..i18n import LANGUAGES, in_language, t
from ..models import Payment, Plan, Subscription, User, utcnow
from ..services.notify import send_email
from .deps import record_event
from .links import pricing_url, verify_account

hooks_router = APIRouter(prefix="/api/hooks")

#: Сколько дней после неудачного списания доступ ещё работает. Витрина повторяет
#: списание каждые BILLING_RETRY_HOURS=48 ч, всего BILLING_MAX_FAILURES=4 раза —
#: последняя попытка через 6 дней после первой. Пока она пытается, человек не
#: должен терять доступ; сдалась — придёт `unpaid`, и это блок. Два дня сверху —
#: на случай, если `unpaid` задержится в outbox витрины.
DUNNING_GRACE_DAYS = 8


class ProviderEvent(BaseModel):
    """Событие провайдера в нашем виде (его собирает витрина, lib/billing.ts)."""

    provider: str = "maib"
    #: имя события у провайдера: subscription_created, subscription_payment_success, …
    event: str
    #: subscription — двигает доступ; payment — только история оплат
    kind: str
    #: id объекта у провайдера: подписки или счёта
    object_id: str
    test_mode: bool = False
    email: str = ""
    name: str = ""
    customer_id: str = ""
    subscription_id: str = ""
    plan: str | None = None
    interval: str | None = None
    #: состояние подписки (on_trial, active, past_due, unpaid, paused,
    #: cancelled, expired) или счёта (paid, pending, void, refunded, partial_refund)
    status: str = ""
    renews_at: str | None = None
    ends_at: str | None = None
    trial_ends_at: str | None = None
    #: когда провайдер последний раз менял объект — для порядка событий
    updated_at: str | None = None
    amount_cents: int = 0
    refunded_cents: int = 0
    currency: str = "EUR"
    billing_reason: str = ""
    #: язык витрины, с которой пришёл покупатель (en | ru | fr | de)
    locale: str | None = None
    #: подписанная ссылка на аккаунт (см. account_token), когда человек
    #: пришёл оплачивать из платформы, а не с витрины
    account: str = ""
    #: личная ссылка витрины «Управлять подпиской» (отмена автопродления, без входа)
    manage_url: str = ""
    # --- для письма-подтверждения оплаты (требование maib) ---
    #: номер заказа, как его видит покупатель на странице оплаты витрины
    order_no: str = ""
    description: str = ""
    #: продавец: название, IDNO, адрес — из lib/legal/operator.ts витрины
    merchant: str = ""
    #: маска карты, RRN и код авторизации банка
    card: str = ""
    rrn: str = ""
    approval: str = ""
    paid_at: str | None = None
    #: почему банк отказал (для письма о неудачном списании)
    status_message: str = ""
    #: следующая попытка списания; пусто — попыток больше не будет
    next_charge_at: str | None = None


@hooks_router.post("/billing")
def billing_hook(
    ev: ProviderEvent,
    request: Request,
    db: Session = Depends(get_db),
    x_billing_secret: str = Header(default=""),
):
    """Принять событие провайдера от витрины.

    Ответ не-2xx заставляет витрину ответить провайдеру ошибкой, и тот повторит
    доставку. Поэтому 5xx — только на сбой, который повтор может исправить.
    Событие, которое не обработать никогда (нет тарифа, нет адреса), отвечает
    200 с `ok: false` и остаётся в журнале аудита для администратора.
    """
    secret = config.BILLING_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(503, "приём оплат не настроен")
    if not hmac.compare_digest(x_billing_secret.encode(), secret.encode()):
        raise HTTPException(401, "неверный секрет")
    return apply_event(db, ev, request)


def apply_event(db: Session, ev: ProviderEvent, request: Request | None = None) -> dict[str, Any]:
    """Применить событие. Отдельно от маршрута — чтобы проверять без HTTP.

    :param db: Сессия
    :param ev: Событие
    :param request: Запрос (для адреса в аудите)
    :returns: Что сделано
    """
    if ev.kind == "subscription":
        return _apply_subscription(db, ev, request)
    if ev.kind == "payment":
        return _apply_payment(db, ev, request)
    return {"ok": True, "ignored": ev.event}


# --------------------------------------------------------------------------
# Подписка
# --------------------------------------------------------------------------


def _apply_subscription(db: Session, ev: ProviderEvent, request: Request | None) -> dict[str, Any]:
    user, created = _find_user(db, ev, create=True)
    if user is None:
        audit(db, request, None, "billing_hook_error",
              f"{ev.event} {ev.object_id}: нет адреса покупателя")
        return {"ok": False, "reason": "no_email"}
    if user.role == "admin":
        audit(db, request, user, "billing_hook_skipped",
              f"{ev.event} {ev.object_id}: аккаунт администратора не трогаем")
        return {"ok": False, "reason": "admin_account"}

    plan = db.get(Plan, ev.plan) if ev.plan else None
    sub = _provider_subscription(db, ev.provider, ev.object_id)
    if sub is None:
        if plan is None:
            audit(db, request, user, "billing_hook_error",
                  f"{ev.event} {ev.object_id}: неизвестный тариф {ev.plan!r} — "
                  "id тарифов в PLANS витрины (lib/site.ts) должны совпадать с кодами тарифов платформы")
            return {"ok": False, "reason": "unknown_plan"}
        now = utcnow()
        sub = Subscription(
            user_id=user.id,
            plan_code=plan.code,
            status="active",
            started_at=now,
            current_period_end=now,
            grace_days=DUNNING_GRACE_DAYS,
            provider=ev.provider,
            external_id=ev.object_id,
            note=f"оплата картой через {ev.provider}",
        )
        db.add(sub)
    else:
        stamp = _parse(ev.updated_at)
        seen = _as_utc(sub.synced_at)
        if stamp is not None and seen is not None and stamp < seen:
            return {"ok": True, "stale": True}
        # тариф меняют в кабинете провайдера — переходим вслед
        if plan is not None:
            sub.plan_code = plan.code

    if ev.customer_id:
        sub.customer_ref = ev.customer_id[:64]
    if ev.manage_url:
        sub.manage_url = ev.manage_url[:512]
    if ev.interval in ("month", "year"):
        sub.billing_interval = ev.interval
    _sync_state(sub, ev)
    sub.synced_at = _parse(ev.updated_at) or utcnow()
    sub.updated_at = utcnow()
    db.commit()
    db.refresh(sub)

    until = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "—"
    record_event(db, user, "subscription", f"{ev.event}: {ev.status}, до {until}", request)
    audit(db, request, user, "billing_subscription",
          f"{ev.event} #{ev.object_id} {sub.plan_code} -> {ev.status} до {until}")

    if created:
        _welcome(db, user, request)
    return {"ok": True, "user_id": user.id, "created": created, "status": sub.status}


def _sync_state(sub: Subscription, ev: ProviderEvent) -> None:
    """Перевести состояние провайдера в наше.

    Наша колонка `status` хранит только решения, которых не вывести из дат
    (см. service.effective_status). Поэтому «отменена, но оплачено до конца
    месяца» — это `active` с концом периода и без льготных дней, а не
    `cancelled`: тот закрыл бы доступ сразу.
    """
    renews = _parse(ev.renews_at)
    ends = _parse(ev.ends_at)
    trial_end = _parse(ev.trial_ends_at)
    end: datetime | None = None

    if ev.status == "on_trial":
        sub.status, sub.trial, sub.cancel_at_period_end = "trialing", 1, 0
        sub.grace_days = DUNNING_GRACE_DAYS
        end = trial_end or renews
    elif ev.status == "active":
        sub.status, sub.trial, sub.cancel_at_period_end = "active", 0, 0
        sub.grace_days = DUNNING_GRACE_DAYS
        end = renews
    elif ev.status == "past_due":
        # списание не прошло, провайдер повторяет. Конец периода не двигаем:
        # он уже в прошлом, и даты сами показывают past_due на время попыток.
        # renews_at здесь — дата следующей попытки, а не оплаченный срок
        sub.status, sub.cancel_at_period_end = "active", 0
        sub.grace_days = max(sub.grace_days or 0, DUNNING_GRACE_DAYS)
    elif ev.status in ("unpaid", "paused"):
        sub.status = "suspended"
    elif ev.status == "cancelled":
        # оплаченный срок дорабатывает до ends_at, дальше — без льготы
        sub.status, sub.cancel_at_period_end, sub.grace_days = "active", 1, 0
        end = ends
    elif ev.status == "expired":
        sub.status, sub.cancel_at_period_end = "cancelled", 1
        end = ends

    if end is not None:
        sub.current_period_end = end


# --------------------------------------------------------------------------
# Оплата
# --------------------------------------------------------------------------


def _apply_payment(db: Session, ev: ProviderEvent, request: Request | None) -> dict[str, Any]:
    # счёт может прийти раньше подписки — тогда аккаунт заводится здесь
    user, created = _find_user(db, ev, create=True)
    if user is None:
        audit(db, request, None, "billing_hook_error",
              f"{ev.event} {ev.object_id}: нет адреса покупателя")
        return {"ok": False, "reason": "no_email"}
    if user.role == "admin":
        audit(db, request, user, "billing_hook_skipped",
              f"{ev.event} {ev.object_id}: аккаунт администратора не трогаем")
        return {"ok": False, "reason": "admin_account"}

    if ev.event == "subscription_payment_failed":
        status = "failed"
    elif ev.event == "subscription_payment_refunded" or ev.status in ("refunded", "partial_refund"):
        status = "refunded" if ev.refunded_cents >= ev.amount_cents else "paid"
    else:
        status = "paid"

    external_id = f"{ev.provider}:invoice:{ev.object_id}"
    payment = db.scalar(select(Payment).where(Payment.external_id == external_id).limit(1))
    net = max(0, ev.amount_cents - ev.refunded_cents)
    is_new = payment is None
    was_paid = not is_new and payment.status == "paid"

    if payment is None:
        # счёт на ноль (пробный период) — не оплата, в историю не пишем
        if status == "paid" and net == 0:
            return {"ok": True, "skipped": "zero_amount"}
        sub = _provider_subscription(db, ev.provider, ev.subscription_id)
        payment = Payment(
            user_id=user.id,
            plan_code=(sub.plan_code if sub else ev.plan) or "",
            amount_cents=net if status == "paid" else ev.amount_cents,
            currency=(ev.currency or "EUR").upper()[:3],
            status=status,
            source=ev.provider,
            external_id=external_id,
            invoice_no=(ev.order_no or ev.object_id[:8].upper())[:32],
            note=_payment_note(ev),
        )
        db.add(payment)
    else:
        # неудача после успеха — это другая попытка того же счёта, а не
        # отмена оплаты: уже полученные деньги не превращаем в «failed»
        if status == "failed" and payment.status == "paid":
            return {"ok": True, "kept": "paid"}
        payment.status = status
        if status == "paid":
            payment.amount_cents = net
        payment.note = _payment_note(ev)
    db.commit()
    db.refresh(payment)

    record_event(db, user, "payment",
                 f"{ev.event}: {payment.amount_cents / 100:.2f} {payment.currency} ({status})",
                 request)
    if created:
        _welcome(db, user, request)
    # письмо — один раз на оплату: повтор события из outbox второго не шлёт
    if status == "paid" and not was_paid and ev.event != "subscription_payment_refunded":
        _receipt(db, user, ev, payment, request)
    elif status == "failed" and ev.billing_reason == "renewal" and is_new:
        _payment_failed(db, user, ev, payment, request)
    return {"ok": True, "user_id": user.id, "payment_id": payment.id, "status": status}


def _payment_note(ev: ProviderEvent) -> str:
    """Короткая пометка к оплате: за что и был ли возврат."""
    reason = {"initial": "первая оплата", "renewal": "продление", "updated": "смена тарифа"}
    parts = [reason.get(ev.billing_reason, ev.billing_reason or ev.event)]
    if ev.card:
        parts.append(f"карта {ev.card}")
    if ev.refunded_cents:
        parts.append(f"возврат {ev.refunded_cents / 100:.2f} {ev.currency.upper()}")
    if ev.test_mode:
        parts.append("ТЕСТ")
    return ", ".join(p for p in parts if p)[:256]


# --------------------------------------------------------------------------
# Покупатель
# --------------------------------------------------------------------------


def _find_user(db: Session, ev: ProviderEvent, *, create: bool) -> tuple[User | None, bool]:
    """Найти владельца события, при необходимости завести аккаунт.

    Сначала по подписке у провайдера (адрес в его кабинете могли сменить),
    потом по e-mail — и в поле адреса, и в логине.

    :returns: Пользователь (или None) и признак «заведён сейчас»
    """
    # пришёл из платформы: аккаунт известен точно, адрес в оплате мог быть другим
    owner = verify_account(ev.account)
    if owner is not None:
        user = db.get(User, owner)
        if user is not None:
            return user, False

    sub = _provider_subscription(db, ev.provider, ev.subscription_id or (
        ev.object_id if ev.kind == "subscription" else ""))
    if sub is not None:
        user = db.get(User, sub.user_id)
        if user is not None:
            return user, False

    email = ev.email.strip().lower()
    if not email or "@" not in email:
        return None, False

    user = db.scalar(
        select(User).where(func.lower(User.email) == email).order_by(User.id).limit(1)
    ) or db.scalar(select(User).where(func.lower(User.username) == email).limit(1))
    if user is not None:
        if not user.email:
            user.email = email
            db.commit()
        return user, False
    if not create:
        return None, False

    user = User(
        username=email[:64],
        # пароля нет ни у кого: человек задаёт его сам через «Забыли пароль?»
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role="user",
        email=email,
        language=ev.locale if ev.locale in LANGUAGES else "en",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True


def _welcome(db: Session, user: User, request: Request | None) -> None:
    """Письмо новому покупателю: логин и как задать пароль."""
    with in_language(user.language):
        subject = t("FX Navigator — доступ открыт")
        body = t(
            "Оплата получена, подписка активна.\n\n"
            "Вход: {0}\nЛогин: {1}\n\n"
            "Пароль ещё не задан. На странице входа нажмите «Забыли пароль?» и "
            "введите логин — придёт код, по нему вы зададите пароль.\n\n"
            "Подтверждение оплаты придёт отдельным письмом.",
            config.PUBLIC_APP_URL,
            user.username,
        )
    sent = send_email(db, user.email, subject, body)
    audit(db, request, user, "account_created_by_purchase",
          "письмо отправлено" if sent else "письмо НЕ ушло — проверьте SMTP")


def _receipt(db: Session, user: User, ev: ProviderEvent, payment: Payment,
             request: Request | None) -> None:
    """Подтверждение оплаты покупателю.

    maib требует его от магазина после каждой оплаты: номер заказа, продавец,
    сумма, валюта, дата, описание. Без этого письма банк не переводит проект
    в рабочий режим.
    """
    to = user.email or ev.email
    if not to:
        return
    with in_language(user.language):
        rows = [
            (t("Номер заказа"), payment.invoice_no),
            (t("Продавец"), ev.merchant),
            (t("Описание"), ev.description),
            (t("Сумма"), f"{payment.amount_cents / 100:.2f} {payment.currency}"),
            (t("Дата"), _fmt_time(_parse(ev.paid_at) or utcnow())),
            (t("Карта"), ev.card),
            (t("Код авторизации"), ev.approval),
            ("RRN", ev.rrn),
            (t("Следующее списание"), _fmt_day(_parse(ev.next_charge_at))),
        ]
        body = t("Оплата прошла успешно.") + "\n\n" + "\n".join(f"{k}: {v}" for k, v in rows if v)
        if ev.manage_url:
            body += "\n\n" + t("Отменить автоматическое продление: {0}", ev.manage_url)
        if ev.test_mode:
            body = t("ТЕСТОВАЯ ОПЛАТА — деньги не списаны.") + "\n\n" + body
        subject = t("FX Navigator — оплата {0}", payment.invoice_no)
    sent = send_email(db, to, subject, body)
    audit(db, request, user, "billing_receipt",
          f"{payment.invoice_no}: " + ("письмо отправлено" if sent else "письмо НЕ ушло — проверьте SMTP"))


def _payment_failed(db: Session, user: User, ev: ProviderEvent, payment: Payment,
                    request: Request | None) -> None:
    """Автоматическое списание не прошло: сказать, когда повтор и как платить другой картой.

    Без письма человек узнаёт об этом только по блоку через неделю: витрина
    пробует молча, а в платформу он может и не заходить.
    """
    to = user.email or ev.email
    if not to:
        return
    amount = f"{ev.amount_cents / 100:.2f} {(ev.currency or 'EUR').upper()}"
    retry = _parse(ev.next_charge_at)
    with in_language(user.language):
        lines = [t("Автоматическое списание {0} не прошло: {1}.", amount, ev.status_message or "—")]
        lines.append(t("Повторим попытку {0}. Доступ пока сохраняется.", _fmt_day(retry)) if retry
                     else t("Попыток больше не будет: доступ приостановлен."))
        lines.append(t("Чтобы платить другой картой, оформите подписку заново: {0}. "
                       "Прежняя подписка отменится сама.",
                       pricing_url(user.id, user.email or ev.email, user.language or "en")))
        subject = t("FX Navigator — оплата не прошла")
    sent = send_email(db, to, subject, "\n\n".join(lines))
    audit(db, request, user, "billing_payment_failed_mail",
          f"{payment.invoice_no}: " + ("письмо отправлено" if sent else "письмо НЕ ушло — проверьте SMTP"))


# --------------------------------------------------------------------------
# Вспомогательное
# --------------------------------------------------------------------------


def _provider_subscription(db: Session, provider: str, external_id: str) -> Subscription | None:
    if not external_id:
        return None
    return db.scalar(
        select(Subscription)
        .where(Subscription.provider == provider, Subscription.external_id == external_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def _parse(value: str | None) -> datetime | None:
    """ISO-время провайдера («…Z» или со смещением) в UTC-aware."""
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _fmt_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else ""


def _fmt_day(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
