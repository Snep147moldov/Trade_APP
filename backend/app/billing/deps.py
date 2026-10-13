"""Проверки подписки для маршрутов и запись активности.

Одна зависимость на все защищённые маршруты. Так проверка живёт в одном месте,
и новый маршрут либо её объявляет, либо не защищён — видно при чтении, а не
через полгода в логах.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth.deps import current_user, get_db
from ..i18n import t
from ..models import User, UserEvent
from .service import (
    EntitlementDenied,
    SubscriptionRequired,
    assert_active,
    assert_allows,
    effective_status,
    get_subscription,
)


def require_subscription(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> User:
    """Маршрут требует активной подписки.

    402 (а не 403) выбрано намеренно: клиент отличает «нужно заплатить» от
    «не ваша роль» и показывает окно оплаты, а не ошибку доступа.

    :param db: Сессия
    :param user: Пользователь
    :returns: Пользователь
    :raises HTTPException: 402, когда подписка не активна
    """
    try:
        assert_active(db, user)
    except SubscriptionRequired as exc:
        raise HTTPException(
            402,
            detail={
                "error": "subscription_required",
                "status": exc.status,
                "message": t("подписка не активна — продлите, чтобы продолжить"),
            },
        ) from exc
    return user


def require_entitlement(key: str, amount: int = 1):
    """Зависимость, требующая конкретного права тарифа.

    :param key: Ключ права (см. billing/plans.py)
    :param amount: Сколько единиц требуется
    :returns: Зависимость FastAPI

    Пример::

        @router.post("/autotrade", dependencies=[Depends(require_entitlement("autotrade"))])
    """

    def dependency(
        db: Session = Depends(get_db), user: User = Depends(current_user)
    ) -> User:
        try:
            assert_allows(db, user, key, amount)
        except SubscriptionRequired as exc:
            raise HTTPException(
                402,
                detail={
                    "error": "subscription_required",
                    "status": exc.status,
                    "message": t("подписка не активна — продлите, чтобы продолжить"),
                },
            ) from exc
        except EntitlementDenied as exc:
            raise HTTPException(
                403,
                detail={
                    "error": "entitlement_denied",
                    "entitlement": exc.key,
                    "limit": exc.limit,
                    "message": t("тариф не включает эту возможность"),
                },
            ) from exc
        return user

    return dependency


def record_event(
    db: Session, user: User | None, kind: str, detail: str = "", request: Request | None = None
) -> None:
    """Записать действие пользователя.

    Отдельно от `audit_log`: тот про действия над системой, этот — про
    активность человека, которую администратор смотрит по аккаунту.

    Никогда не роняет вызывающий код: потерянная строка журнала не повод
    отказать в действии, ради которого человек пришёл.

    :param db: Сессия
    :param user: Пользователь (None — аноним, не пишем)
    :param kind: Вид события: login, login_failed, signal_created, …
    :param detail: Короткое описание
    :param request: Запрос, чтобы взять адрес
    """
    if user is None:
        return
    try:
        ip = ""
        if request is not None:
            ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or (request.client.host if request.client else "")
            )
        db.add(UserEvent(user_id=user.id, kind=kind, detail=detail[:512], ip=ip[:64]))
        db.commit()
    except Exception:
        db.rollback()


def subscription_state(db: Session, user: User) -> str:
    """Текущее состояние подписки пользователя.

    :param db: Сессия
    :param user: Пользователь
    :returns: Состояние
    """
    return effective_status(get_subscription(db, user.id))
