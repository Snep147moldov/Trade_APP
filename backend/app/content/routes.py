"""Тексты витрины: публичное чтение и правка из админки.

Сайт-витрина хранит свой текст в коде (английский оригинал плюс словарь
переводов). Эта таблица лежит поверх: где есть запись — показывается она, где
нет — то, что в коде. Поэтому правка не требует выката, а неудачную правку
можно просто удалить и получить исходный текст, не помня, каким он был.

Публичный маршрут отдаёт только карту «строка → текст» для одного языка. Он
без авторизации намеренно: его читает сайт при отрисовке, и уйти оттуда может
только то, что и так напечатано на странице.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..auth.deps import audit, get_db, require_admin
from ..i18n import LANGUAGES
from ..models import ContentOverride, User, utcnow

content_router = APIRouter(prefix="/api/content")
admin_content_router = APIRouter(prefix="/api/admin/content")


@content_router.get("/{locale}")
def public_content(locale: str, db: Session = Depends(get_db)):
    """Правки текста для одного языка — то, что читает сайт.

    Без авторизации: это текст, который и так виден на странице. Неизвестный
    язык отдаёт пустую карту, а не ошибку — сайт в этом случае просто
    показывает то, что в коде.
    """
    if locale not in LANGUAGES:
        return {"locale": locale, "overrides": {}}
    rows = db.scalars(select(ContentOverride).where(ContentOverride.locale == locale)).all()
    return {
        "locale": locale,
        "overrides": {row.source: row.value for row in rows},
        # по этому значению сайт понимает, что кэш пора сбросить
        "version": max((int(r.updated_at.timestamp()) for r in rows), default=0),
    }


@admin_content_router.get("")
def list_overrides(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Все правки по всем языкам — для таблицы в админке."""
    rows = db.scalars(select(ContentOverride).order_by(ContentOverride.updated_at.desc())).all()
    return [
        {
            "source": r.source,
            "locale": r.locale,
            "value": r.value,
            "updated_by": r.updated_by,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


class OverrideInput(BaseModel):
    source: str
    locale: str
    value: str


@admin_content_router.put("")
def save_override(
    req: OverrideInput,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Переписать строку на одном языке.

    Пустое значение считается возвратом к исходному тексту: отдельная кнопка
    «удалить правку» и пустое поле — для человека одно и то же действие, и
    расходиться они не должны.
    """
    locale = req.locale if req.locale in LANGUAGES else "en"
    value = req.value.strip()

    existing = db.scalar(
        select(ContentOverride).where(
            ContentOverride.source == req.source, ContentOverride.locale == locale
        )
    )
    if not value:
        if existing is not None:
            db.delete(existing)
            db.commit()
            audit(db, request, admin, "content_reverted", f"{locale}: {req.source[:80]}")
        return {"ok": True, "reverted": True}

    if existing is None:
        existing = ContentOverride(source=req.source, locale=locale)
        db.add(existing)
    existing.value = value
    existing.updated_by = admin.username
    existing.updated_at = utcnow()
    db.commit()
    audit(db, request, admin, "content_saved", f"{locale}: {req.source[:80]}")
    return {"ok": True, "reverted": False}


@admin_content_router.delete("")
def clear_all(
    request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """Снять все правки разом — аварийный возврат к тексту из кода."""
    count = db.scalar(select(func.count()).select_from(ContentOverride)) or 0
    db.execute(delete(ContentOverride))
    db.commit()
    audit(db, request, admin, "content_cleared", str(count))
    return {"ok": True, "removed": int(count)}
