"""Куда вести человека платить: страница тарифов витрины и подписанная ссылка на аккаунт.

Человек, который платит из платформы, может ввести в оплате другой адрес —
или у его аккаунта адреса нет вовсе. Чтобы оплата не завела второй аккаунт,
кнопка «Оплатить» несёт на витрину подписанный id; витрина хранит его в
подписке (data/billing.db) и возвращает в billing/provider.py с каждым событием.
Подпись — общим секретом витрины и платформы: подделать id чужого аккаунта
нельзя, а подписанный даёт ровно одно — заплатить за этот аккаунт.

Модуль без зависимостей от сервиса и моделей: его читают и service.py, и
provider.py, и любой импорт отсюда в обратную сторону дал бы цикл.
"""

from __future__ import annotations

import hmac
from urllib.parse import urlencode

from .. import config

#: Языки витрины: страница тарифов существует только на них.
SITE_LOCALES = ("en", "ru", "fr", "de")


def account_token(user_id: int) -> str:
    """Подписанный id аккаунта для ссылки на оплату. Пусто, если приём выключен."""
    secret = config.BILLING_WEBHOOK_SECRET
    if not secret:
        return ""
    sig = hmac.new(secret.encode(), f"account:{user_id}".encode(), "sha256").hexdigest()[:32]
    return f"{user_id}.{sig}"


def verify_account(token: str) -> int | None:
    """id аккаунта из подписанной ссылки или None, если подпись не сходится."""
    uid, _, sig = (token or "").partition(".")
    if not uid.isdigit() or not sig:
        return None
    expected = account_token(int(uid))
    if not expected or not hmac.compare_digest(expected, token):
        return None
    return int(uid)


def pricing_url(user_id: int, email: str, language: str) -> str:
    """Страница тарифов витрины, привязанная к аккаунту."""
    locale = language if language in SITE_LOCALES else "en"
    query = {k: v for k, v in (("for", account_token(user_id)), ("email", email)) if v}
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{config.PUBLIC_SITE_URL}/{locale}/pricing{suffix}#pricing"
