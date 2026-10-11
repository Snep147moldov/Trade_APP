from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..i18n import set_request_language
from ..models import AuditLog, AuthToken, User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, t("требуется вход"))
    token = authorization.removeprefix("Bearer ").strip()
    row = db.get(AuthToken, token)
    if row is None or _as_utc(row.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(401, t("сессия истекла — войдите заново"))
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(401, t("пользователь не найден"))
    # дальше по запросу всё, что видит пользователь, переводится на его язык
    set_request_language(user.language)
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, t("нужны права администратора"))
    return user


def audit(db: Session, request: Request | None, user: User | None,
          action: str, detail: str = "") -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "",
        action=action,
        detail=detail[:500],
        ip=(request.client.host if request and request.client else ""),
    ))
    db.commit()
