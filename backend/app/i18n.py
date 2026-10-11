"""Язык пользовательских текстов: интерфейсные ответы API и уведомления.

Строки в коде остаются русскими — на них же написано приложение, и они служат
ключами словаря. Промах по словарю возвращает оригинал: непереведённое видно
как русский текст, а не как пустое место или `risk.sl_too_close`.

Язык берётся из контекста запроса (его ставит зависимость `current_user`), а
вне запроса — из языка владельца установки: планировщик шлёт в Telegram от
своего имени, HTTP-запроса там нет.
"""

from contextvars import ContextVar

from .translations import TRANSLATIONS

LANGUAGES: tuple[str, ...] = ("en", "ru", "fr", "de")
SOURCE_LANGUAGE = "ru"

# «за пределами запроса» — планировщик, фоновые задачи, CLI
_fallback = SOURCE_LANGUAGE
_current: ContextVar[str | None] = ContextVar("ui_language", default=None)


def set_request_language(lang: str | None) -> None:
    _current.set(lang if lang in LANGUAGES else None)


def set_fallback_language(lang: str | None) -> None:
    """Язык фоновых уведомлений. Вызывается при старте и при смене языка."""
    global _fallback
    if lang in LANGUAGES:
        _fallback = lang


def get_language() -> str:
    return _current.get() or _fallback


def t(ru: str, *args: object) -> str:
    """Перевод русской строки. Подстановки нумерованные: `t("Стоп {0}", x)`.

    Нумерованные, а не именованные: исходники переписывались автоматически из
    f-строк, а порядок аргументов — единственное, что в них однозначно."""
    lang = get_language()
    text = ru if lang == SOURCE_LANGUAGE else (TRANSLATIONS.get(ru, {}).get(lang) or ru)
    if args:
        try:
            text = text.format(*args)
        except (IndexError, KeyError):
            # перевод с испорченными местами подстановки не должен ронять
            # отправку уведомления — показываем оригинал
            text = ru.format(*args)
    return text


# ИИ пишет текст сам, переводить его нечем — язык задаётся в промпте.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ru": "Russian (русский)",
    "fr": "French (français)",
    "de": "German (deutsch)",
}


def answer_language_clause() -> str:
    """Строка для системного промпта: на каком языке писать ответ.

    Сам промпт остаётся русским — модель его понимает, а переводить инструкции
    ради смены языка ответа незачем. Указание ставится последним, чтобы
    перебить «по-русски», оставшееся внутри промптов."""
    return (
        "\n\nIMPORTANT: write the entire answer in "
        f"{LANGUAGE_NAMES.get(get_language(), 'English')}. "
        "This overrides any language mentioned earlier in this prompt."
    )
