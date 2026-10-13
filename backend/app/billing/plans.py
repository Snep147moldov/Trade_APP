"""Тарифы и права: что именно разрешает подписка.

Права — словарь данных, а не ветки `if plan == "pro"` по коду. Причина
практическая: тариф меняют чаще, чем выкатывают релиз, а разбросанные по
двадцати файлам сравнения кодов тарифов расходятся через месяц.

Ключи фиксированы ({@link ENTITLEMENT_KEYS}) — незнакомый ключ в базе
игнорируется, а отсутствующий берётся из {@link DEFAULT_ENTITLEMENTS}. Так
тариф, заведённый до появления нового права, не отбирает его молча.
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------
# Права
# --------------------------------------------------------------------------

#: Что умеет каждое право и каким значением выражается.
#:
#: Числовое право — предел (0 = запрещено, -1 = без предела). Логическое —
#: да/нет. Список — перечень разрешённых значений.
ENTITLEMENT_KEYS: dict[str, str] = {
    "max_instruments": "сколько инструментов можно держать в «Избранном» (-1 = без предела)",
    "timeframes": "какие таймфреймы доступны",
    "autotrade": "разрешена ли автоторговля",
    "mt5": "можно ли подключить счёт MT5",
    "max_open_signals": "сколько сигналов может быть открыто одновременно",
    "ai_per_day": "сколько ИИ-анализов в сутки",
    "backtest": "доступен ли бэктест",
    "history_days": "за сколько дней видна история (-1 = вся)",
    "telegram": "можно ли подключить Telegram",
    "api_access": "доступ к API для внешних клиентов",
    "support": "уровень поддержки: community | email | priority",
}

#: Значения для права, которого нет в тарифе. Намеренно скромные: новое право
#: не должно появиться у всех разом только потому, что его забыли прописать.
DEFAULT_ENTITLEMENTS: dict[str, Any] = {
    "max_instruments": 5,
    "timeframes": ["1h", "4h"],
    "autotrade": False,
    "mt5": False,
    "max_open_signals": 3,
    "ai_per_day": 0,
    "backtest": False,
    "history_days": 30,
    "telegram": True,
    "api_access": False,
    "support": "community",
}

# --------------------------------------------------------------------------
# Тарифы по умолчанию
# --------------------------------------------------------------------------

#: Тарифы, которыми установка заводится при первом запуске. Дальше их меняет
#: администратор, и повторный запуск их не перезаписывает.
DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "trial",
        "name": "Trial",
        "description": "14 дней, чтобы посмотреть на свои инструменты",
        "price_cents": 0,
        "period_days": 14,
        "sort": 0,
        "entitlements": {
            "max_instruments": 5,
            "timeframes": ["1h", "4h"],
            "autotrade": False,
            "mt5": False,
            "max_open_signals": 3,
            "ai_per_day": 3,
            "backtest": False,
            "history_days": 14,
            "telegram": True,
            "api_access": False,
            "support": "community",
        },
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "Графики, скринер и уведомления",
        "price_cents": 2900,
        "period_days": 30,
        "sort": 1,
        "entitlements": {
            "max_instruments": 10,
            "timeframes": ["15m", "1h", "4h"],
            "autotrade": False,
            "mt5": False,
            "max_open_signals": 5,
            "ai_per_day": 10,
            "backtest": False,
            "history_days": 90,
            "telegram": True,
            "api_access": False,
            "support": "email",
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "Автоторговля, MT5, бэктест и ИИ-анализ",
        "price_cents": 7900,
        "period_days": 30,
        "sort": 2,
        "entitlements": {
            "max_instruments": 40,
            "timeframes": ["5m", "15m", "1h", "4h", "1d"],
            "autotrade": True,
            "mt5": True,
            "max_open_signals": 20,
            "ai_per_day": 100,
            "backtest": True,
            "history_days": -1,
            "telegram": True,
            "api_access": True,
            "support": "priority",
        },
    },
    {
        "code": "desk",
        "name": "Desk",
        "description": "Для наставников и небольших команд",
        "price_cents": 19900,
        "period_days": 30,
        "sort": 3,
        "entitlements": {
            "max_instruments": -1,
            "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
            "autotrade": True,
            "mt5": True,
            "max_open_signals": -1,
            "ai_per_day": -1,
            "backtest": True,
            "history_days": -1,
            "telegram": True,
            "api_access": True,
            "support": "priority",
        },
    },
]


def merged_entitlements(plan_entitlements: dict[str, Any] | None) -> dict[str, Any]:
    """Права тарифа, дополненные значениями по умолчанию.

    Ключи, которых нет в {@link ENTITLEMENT_KEYS}, отбрасываются: случайная
    опечатка в админке не должна создавать право, которое никто не проверяет.

    :param plan_entitlements: Права, записанные в тарифе
    :returns: Полный набор прав
    """
    merged = dict(DEFAULT_ENTITLEMENTS)
    for key, value in (plan_entitlements or {}).items():
        if key in ENTITLEMENT_KEYS:
            merged[key] = value
    return merged


def allows(entitlements: dict[str, Any], key: str, amount: int = 1) -> bool:
    """Разрешает ли право действие.

    :param entitlements: Полный набор прав
    :param key: Ключ права
    :param amount: Сколько единиц требуется (для числовых прав)
    :returns: True, когда действие разрешено

    >>> allows({"max_open_signals": -1}, "max_open_signals", 99)
    True
    >>> allows({"autotrade": False}, "autotrade")
    False
    """
    value = entitlements.get(key, DEFAULT_ENTITLEMENTS.get(key))
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value < 0 or amount <= value
    return bool(value)
