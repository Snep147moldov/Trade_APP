"""Удаление аккаунта: что уходит вместе с человеком, а что остаётся.

Уходит то, что без человека смысла не имеет и что политика приватности обещает
удалить: сессии, доступ (подписки), напоминания об оплате, активность, заметки
CRM. Остаются:

- оплаты — бухгалтерия, их обязаны хранить. К пометке дописывается имя
  удалённого аккаунта: в списке оплат его больше не с кем сопоставить;
- журнал аудита — след безопасности, имя в нём записано на момент действия.

Оставшиеся строки указывают на id, который больше никому не выдаётся (users
создана с AUTOINCREMENT, см. database._never_reuse_user_ids), поэтому новый
аккаунт их не унаследует.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..billing.service import ACTIVE_STATES, effective_status, get_subscription
from ..models import (AuthToken, BillingNotice, CustomerProfile, Payment, Subscription,
                      User, UserEvent)

#: Удаляется вместе с аккаунтом.
DELETED_WITH_USER = (AuthToken, Subscription, BillingNotice, UserEvent, CustomerProfile)


def renewing_subscription(db: Session, user: User) -> Subscription | None:
    """Подписка, с карты по которой витрина ещё будет списывать.

    Пока она есть, удалять аккаунт нельзя: maib продолжит списывать деньги
    с человека, у которого больше нет доступа.
    """
    sub = get_subscription(db, user.id)
    if (sub is not None and sub.provider and not sub.cancel_at_period_end
            and effective_status(sub) in ACTIVE_STATES):
        return sub
    return None


def delete_account(db: Session, user: User) -> dict[str, int]:
    """Удалить аккаунт и всё, что без него не нужно.

    :param db: Сессия
    :param user: Аккаунт
    :returns: Сколько строк удалено по таблицам (и сколько оплат осталось)
    """
    removed: dict[str, int] = {}
    for model in DELETED_WITH_USER:
        removed[model.__tablename__] = db.execute(
            delete(model).where(model.user_id == user.id)).rowcount or 0
    kept = db.scalars(select(Payment).where(Payment.user_id == user.id)).all()
    for payment in kept:
        mark = f"аккаунт {user.username} удалён"
        if mark not in (payment.note or ""):
            payment.note = (f"{payment.note}; {mark}" if payment.note else mark)[:256]
    removed["payments_kept"] = len(kept)
    db.delete(user)
    db.commit()
    return removed
