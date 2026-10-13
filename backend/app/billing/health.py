"""Оценка здоровья клиента: насколько он близок к уходу.

Одно число 0–100 и список причин, почему оно такое. Число без причин
бесполезно: администратор всё равно пойдёт смотреть, что случилось, и
единственное, что меняется, — потраченное на это время.

Подход взят из CRM-карточек: оценка складывается из нескольких признаков,
каждый со своим весом, и каждый возвращает понятную человеку фразу.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

#: Максимум по каждому признаку. Сумма — 100.
WEIGHTS = {
    "subscription": 40,
    "recency": 25,
    "payments": 20,
    "usage": 15,
}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def customer_health(
    *,
    status: str,
    days_left: int | None,
    last_seen: datetime | None,
    payments: int,
    events_30d: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Оценка и объяснение.

    :param status: Состояние подписки
    :param days_left: Дней до конца периода (отрицательное — просрочено)
    :param last_seen: Последний вход
    :param payments: Сколько раз оплатил
    :param events_30d: Сколько действий за 30 дней
    :param now: Текущее время (для тестов)
    :returns: `{"score": 0..100, "factors": [{"label", "points", "max"}]}`

    >>> customer_health(status="active", days_left=20, last_seen=None, payments=0, events_30d=0)["score"] < 60
    True
    """
    moment = now or datetime.now(timezone.utc)
    factors: list[dict[str, Any]] = []

    # 1. Подписка: приостановленная — главный признак ухода
    if status in ("active", "trialing"):
        sub_points = WEIGHTS["subscription"]
        sub_text = "подписка активна"
        if days_left is not None and days_left <= 3:
            sub_points = int(WEIGHTS["subscription"] * 0.6)
            sub_text = f"период кончается через {days_left} дн."
    elif status == "past_due":
        sub_points = int(WEIGHTS["subscription"] * 0.3)
        sub_text = "оплата просрочена"
    else:
        sub_points = 0
        sub_text = f"подписка: {status}"
    factors.append({"label": sub_text, "points": sub_points, "max": WEIGHTS["subscription"]})

    # 2. Давность визита: молчание дольше двух недель — тревожный признак
    seen = _aware(last_seen)
    if seen is None:
        rec_points, rec_text = 0, "ни разу не входил"
    else:
        days = (moment - seen).days
        if days <= 2:
            rec_points, rec_text = WEIGHTS["recency"], "заходил на днях"
        elif days <= 7:
            rec_points, rec_text = int(WEIGHTS["recency"] * 0.7), f"последний вход {days} дн. назад"
        elif days <= 30:
            rec_points, rec_text = int(WEIGHTS["recency"] * 0.3), f"не заходил {days} дн."
        else:
            rec_points, rec_text = 0, f"не заходил {days} дн."
    factors.append({"label": rec_text, "points": rec_points, "max": WEIGHTS["recency"]})

    # 3. История оплат: платил — значит продукт уже доказал ценность
    pay_points = min(WEIGHTS["payments"], payments * 7)
    pay_text = "ни одной оплаты" if payments == 0 else f"оплат: {payments}"
    factors.append({"label": pay_text, "points": pay_points, "max": WEIGHTS["payments"]})

    # 4. Использование: аккаунт, которым не пользуются, не продлевают
    use_points = min(WEIGHTS["usage"], events_30d // 2)
    use_text = "нет активности за месяц" if events_30d == 0 else f"действий за месяц: {events_30d}"
    factors.append({"label": use_text, "points": use_points, "max": WEIGHTS["usage"]})

    return {
        "score": sum(f["points"] for f in factors),
        "factors": factors,
    }


def health_band(score: int) -> str:
    """Короткая характеристика оценки.

    :param score: 0–100
    :returns: good | watch | risk
    """
    if score >= 70:
        return "good"
    if score >= 40:
        return "watch"
    return "risk"
