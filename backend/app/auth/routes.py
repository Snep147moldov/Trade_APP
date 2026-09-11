from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, AuthToken, User
from ..services.notify import send_email
from .deps import audit, current_user, get_db, require_admin
from .security import (
    TOKEN_TTL_DAYS,
    hash_password,
    new_token,
    new_totp_secret,
    totp_uri,
    verify_password,
    verify_totp,
)

auth_router = APIRouter(prefix="/api/auth")   # public: login only
admin_router = APIRouter(prefix="/api/admin")  # guarded per-route


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "role": u.role,
        "totp_enabled": bool(u.totp_enabled),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# --------------------------------------------------------------------------
# Login / logout / me
# --------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


@auth_router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == req.username.strip()))
    if user is None or not verify_password(req.password, user.password_hash):
        audit(db, request, user, "login_fail", f"попытка входа: {req.username}")
        raise HTTPException(401, "неверный логин или пароль")

    if user.totp_enabled:
        if not req.totp_code:
            return {"requires_totp": True}
        if not verify_totp(user.totp_secret or "", req.totp_code):
            audit(db, request, user, "login_fail", "неверный код 2FA")
            raise HTTPException(401, "неверный код двухфакторной аутентификации")

    token = new_token()
    db.add(AuthToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    ))
    db.commit()
    audit(db, request, user, "login_ok")
    return {"token": token, "user": _user_out(user)}


@auth_router.post("/logout")
def logout(request: Request, authorization: str | None = Header(default=None),
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    if authorization and authorization.startswith("Bearer "):
        row = db.get(AuthToken, authorization.removeprefix("Bearer ").strip())
        if row:
            db.delete(row)
            db.commit()
    audit(db, request, user, "logout")
    return {"ok": True}


@auth_router.get("/me")
def me(user: User = Depends(current_user)):
    return _user_out(user)


# --------------------------------------------------------------------------
# Account settings: password + 2FA
# --------------------------------------------------------------------------

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@auth_router.post("/change-password")
def change_password(req: PasswordChange, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(400, "текущий пароль неверен")
    if len(req.new_password) < 8:
        raise HTTPException(400, "новый пароль должен быть не короче 8 символов")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    audit(db, request, user, "password_change")
    return {"ok": True}


@auth_router.post("/2fa/setup")
def totp_setup(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.totp_enabled:
        raise HTTPException(400, "2FA уже включена")
    secret = new_totp_secret()
    user.totp_secret = secret
    db.commit()
    return {"secret": secret, "uri": totp_uri(secret, user.username)}


class TotpCode(BaseModel):
    code: str


@auth_router.post("/2fa/enable")
def totp_enable(req: TotpCode, request: Request,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.totp_secret:
        raise HTTPException(400, "сначала вызовите /2fa/setup")
    if not verify_totp(user.totp_secret, req.code):
        raise HTTPException(400, "код не подошёл — проверьте приложение-аутентификатор")
    user.totp_enabled = 1
    db.commit()
    audit(db, request, user, "2fa_enabled")
    return {"ok": True}


@auth_router.post("/2fa/disable")
def totp_disable(req: TotpCode, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.totp_enabled:
        raise HTTPException(400, "2FA не включена")
    if not verify_totp(user.totp_secret or "", req.code):
        raise HTTPException(400, "неверный код")
    user.totp_enabled = 0
    user.totp_secret = None
    db.commit()
    audit(db, request, user, "2fa_disabled")
    return {"ok": True}


# --------------------------------------------------------------------------
# Admin: users + audit log
# --------------------------------------------------------------------------

@admin_router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [_user_out(u) for u in users]


class NewUser(BaseModel):
    username: str
    password: str
    role: str = "user"
    # без адреса восстановление доступа для этой учётной записи недоступно —
    # пароль сможет сменить только админ
    email: str = ""


@admin_router.post("/users")
def create_user(req: NewUser, request: Request,
                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    username = req.username.strip()
    if len(username) < 3:
        raise HTTPException(400, "логин не короче 3 символов")
    if len(req.password) < 8:
        raise HTTPException(400, "пароль не короче 8 символов")
    if req.role not in ("admin", "user"):
        raise HTTPException(400, "роль: admin или user")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "такой логин уже существует")
    user = User(username=username, password_hash=hash_password(req.password),
                role=req.role, email=req.email.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, request, admin, "user_created", f"{username} ({req.role})")
    return _user_out(user)


@admin_router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request,
                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "нельзя удалить собственный аккаунт")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "пользователь не найден")
    for t in db.scalars(select(AuthToken).where(AuthToken.user_id == user_id)).all():
        db.delete(t)
    db.delete(user)
    db.commit()
    audit(db, request, admin, "user_deleted", user.username)
    return {"ok": True}


@admin_router.get("/audit")
def audit_log(limit: int = 200, db: Session = Depends(get_db),
              _: User = Depends(require_admin)):
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 1000))
    ).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "username": r.username,
            "action": r.action,
            "detail": r.detail,
            "ip": r.ip,
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# Восстановление доступа
#
# Код уходит на адрес, привязанный к УЧЁТНОЙ ЗАПИСИ, а не на общий ящик из
# настроек уведомлений: по общему ящику любой заведённый пользователь смог бы
# сбросить чужой пароль, в том числе админский.
#
# Ответ всегда одинаковый. Иначе форма превращается в проверку, заведён ли
# такой логин, — а это первая половина подбора пароля.
# --------------------------------------------------------------------------

RESET_TTL_MIN = 15
_SAME_ANSWER = {
    "ok": True,
    "detail": (
        "Если логин существует и к нему привязана почта, код отправлен. "
        "Он действует 15 минут."
    ),
}


class ForgotRequest(BaseModel):
    username: str


class ResetRequest(BaseModel):
    username: str
    code: str
    new_password: str


def _mask(addr: str) -> str:
    name, _, dom = addr.partition("@")
    head = name[:2] if len(name) > 2 else name[:1]
    return f"{head}{'*' * max(3, len(name) - len(head))}@{dom}"


@auth_router.post("/forgot")
def forgot_password(req: ForgotRequest, request: Request,
                    db: Session = Depends(get_db)):
    import secrets

    user = db.scalar(select(User).where(User.username == req.username.strip()))
    if user is None or not user.email:
        audit(db, request, user, "reset_request",
              f"запрос сброса: {req.username} (без адреса или нет пользователя)")
        return _SAME_ANSWER

    code = f"{secrets.randbelow(1_000_000):06d}"
    user.reset_hash = hash_password(code)
    user.reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MIN)
    db.commit()

    sent = send_email(
        db, user.email, "Aurex — код восстановления",
        f"Код для смены пароля: {code}\n\n"
        f"Действует {RESET_TTL_MIN} минут. Если вы этого не запрашивали — "
        f"просто не вводите его, пароль останется прежним.",
    )
    audit(db, request, user, "reset_request",
          f"код выслан на {_mask(user.email)}" if sent else "отправка не удалась")
    return _SAME_ANSWER


@auth_router.post("/reset")
def reset_password(req: ResetRequest, request: Request,
                   db: Session = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(400, "пароль короче 8 символов")

    user = db.scalar(select(User).where(User.username == req.username.strip()))
    now = datetime.now(timezone.utc)
    expires = user.reset_expires_at if user else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if (user is None or not user.reset_hash or expires is None or expires < now
            or not verify_password(req.code.strip(), user.reset_hash)):
        audit(db, request, user, "reset_fail", f"неверный код: {req.username}")
        raise HTTPException(400, "код неверный или истёк")

    user.password_hash = hash_password(req.new_password)
    # код одноразовый: гасим вместе со всеми активными сессиями, иначе тот, кто
    # уже был внутри по старому паролю, там и останется
    user.reset_hash = None
    user.reset_expires_at = None
    for t in db.scalars(select(AuthToken).where(AuthToken.user_id == user.id)).all():
        db.delete(t)
    db.commit()
    audit(db, request, user, "reset_ok", "пароль изменён по коду")
    return {"ok": True, "detail": "Пароль изменён. Войдите с новым паролем."}


class EmailChange(BaseModel):
    email: str


@auth_router.post("/email")
def change_email(req: EmailChange, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Адрес для восстановления доступа. Пустая строка — отключить
    восстановление: тогда пароль меняет только администратор."""
    addr = req.email.strip()
    if addr and ("@" not in addr or "." not in addr.rpartition("@")[2]):
        raise HTTPException(400, "адрес выглядит некорректно")
    user.email = addr
    db.commit()
    audit(db, request, user, "email_changed", addr or "адрес удалён")
    return _user_out(user)
