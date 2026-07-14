"""Единая доставка уведомлений: в приложение (БД), Telegram, e-mail (SMTP)."""

import asyncio
import smtplib
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notification
from .runtime import get_app_config, get_credentials
from .telegram import send_message


def add_notification(db: Session, title: str, body: str, kind: str = "alert",
                     instrument: str = "", source: str = "alert") -> Notification:
    row = Notification(title=title[:200], body=body[:2000], kind=kind,
                       instrument=instrument, source=source)
    db.add(row)
    db.commit()
    return row


def _send_email_sync(creds: dict, to_addr: str, subject: str, body: str) -> bool:
    host = creds.get("smtp_host", "")
    if not host or not to_addr:
        return False
    try:
        port = int(creds.get("smtp_port") or 587)
    except ValueError:
        port = 587
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = creds.get("smtp_from") or creds.get("smtp_user") or "alerts@localhost"
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(host, port, timeout=15) as srv:
            srv.ehlo()
            try:
                srv.starttls()
                srv.ehlo()
            except smtplib.SMTPException:
                pass  # plain SMTP servers
            if creds.get("smtp_user"):
                srv.login(creds["smtp_user"], creds.get("smtp_password", ""))
            srv.sendmail(msg["From"], [to_addr], msg.as_string())
        return True
    except Exception:
        return False


async def deliver(db: Session, title: str, body: str,
                  channels: list[str] | None = None, kind: str = "alert",
                  instrument: str = "", source: str = "alert") -> dict[str, bool]:
    """channels: subset of ["app", "telegram", "email"]; None = app only."""
    channels = channels or ["app"]
    creds = get_credentials(db)
    cfg = get_app_config(db)
    result = {"app": False, "telegram": False, "email": False}

    if "app" in channels:
        add_notification(db, title, body, kind, instrument, source)
        result["app"] = True
    if "telegram" in channels and cfg["telegram_enabled"]:
        r = await send_message(creds["telegram_bot_token"], cfg["telegram_chat_id"],
                               f"🔔 <b>{title}</b>\n{body}")
        result["telegram"] = r.get("ok", False)
    if "email" in channels and cfg.get("alert_email"):
        result["email"] = await asyncio.to_thread(
            _send_email_sync, creds, cfg["alert_email"], title, body)
    return result


def list_notifications(db: Session, limit: int = 50,
                       unread_only: bool = False) -> list[dict[str, Any]]:
    q = select(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        q = q.where(Notification.read == 0)
    rows = db.scalars(q.limit(limit)).all()
    return [{
        "id": r.id, "kind": r.kind, "title": r.title, "body": r.body,
        "instrument": r.instrument, "read": bool(r.read), "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


def mark_read(db: Session, ids: list[int] | None = None) -> int:
    q = select(Notification).where(Notification.read == 0)
    if ids:
        q = q.where(Notification.id.in_(ids))
    rows = db.scalars(q).all()
    for r in rows:
        r.read = 1
    db.commit()
    return len(rows)
