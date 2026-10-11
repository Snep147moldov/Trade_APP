"""Telegram inline-button loop: «Купить в MT5 / Пропустить» под сигналами.

Long-polls getUpdates in its own background task (webhooks would need a
public HTTPS domain — the app often runs on a bare IP). The confirmed
update offset is persisted in the DB so a restart never replays an old
button press into a duplicate trade.

Only callbacks coming from the configured telegram_chat_id are honored.
"""

import asyncio
import contextlib
import re
from datetime import datetime, timezone
from typing import Any

from ..database import SessionLocal
from ..models import Setting, Signal
from .runtime import get_app_config, get_credentials
from .telegram import answer_callback, clear_buttons, get_updates, send_message
from ..config import ORDER_TAG
from ..i18n import t

_OFFSET_KEY = "telegram_updates"
MAX_CALLBACK_AGE = 6 * 3600  # кнопка старше 6ч — сигнал наверняка неактуален


def _load_offset(db) -> int:
    row = db.get(Setting, _OFFSET_KEY)
    return int((row.value or {}).get("offset", 0)) if row else 0


def _save_offset(db, offset: int) -> None:
    row = db.get(Setting, _OFFSET_KEY)
    if row:
        row.value = {"offset": offset}
    else:
        db.add(Setting(key=_OFFSET_KEY, value={"offset": offset}))
    db.commit()


async def _open_from_signal(db, sig: Signal, cfg: dict,
                            orders: int | None = None,
                            force_risk: bool = False) -> tuple[str, dict | None]:
    """Кнопка «Купить ×N»: открывает выбранное число ордеров по сохранённым
    уровням сигнала (без N — рекомендация движка).

    Возвращает (текст, клавиатура). Клавиатура не None только в одном случае:
    объём влезает лишь с превышением заданного риска — тогда сделка НЕ
    открывается, а пользователю выдаётся отдельная кнопка подтверждения
    именно этого превышения. `force_risk=True` приходит уже с той кнопки."""
    from .candles import price_precision
    from . import mt5 as mt5_svc
    from .scheduler import autotrade_order_count
    from .settings import settings_for_instrument

    from .tracking import may_send_to_broker

    creds = get_credentials(db)
    if not mt5_svc.is_configured(creds):
        return t("❌ MT5 не подключён — откройте «Подключения» в приложении."), None
    if sig.status != "open":
        return t("⏸ Сигнал #{0} уже закрыт ({1}) — вход неактуален.", f"{sig.id}", f"{sig.status}"), None
    # последний рубеж: отклонённый или просроченный сигнал не исполняется,
    # даже если кнопка пришла (старое сообщение, повтор, гонка)
    if not may_send_to_broker(sig):
        return (t("⛔️ Сигнал #{0} не подтверждён ({1}) — сделка не открыта.", f"{sig.id}", f"{sig.confirm_state}"), None)

    # дедупликация: по этому сигналу уже есть позиция у брокера
    pos = await mt5_svc.positions(db)
    if pos.get("ok"):
        pat = re.compile(rf"#{sig.id}(\D|$)")
        if any(pat.search(p.get("comment") or "") for p in pos["positions"]):
            return t("ℹ️ По сигналу #{0} позиция уже открыта.", f"{sig.id}"), None

    n = orders if orders else autotrade_order_count(cfg, (sig.confidence or 0) * 100)
    n = max(1, min(n, 5))

    settings = settings_for_instrument(db, sig.instrument)
    check = mt5_svc.executability(cfg, settings, sig.instrument,
                                  sig.units, sig.risk_amount, orders=n)
    if not check["ok"]:
        return (t("⛔️ Сигнал #{0} неисполним: {1}. Сделка не открыта.", f"{sig.id}", f"{check['reason']}"), None)
    if check["needs_confirm"] and not force_risk:
        # НЕ открываем: сначала пользователь должен согласиться именно на
        # превышение риска по этой сделке
        return (
            t("⚠️ <b>Сигнал #{0}: превышение риска</b>\n{1} · {2}.\n\nЗаданный риск: {3}€\nРеальный риск: <b>{4}€</b> (×{5}) при {6} лот ×{7}\n\nОткрыть ТОЛЬКО эту сделку с повышенным риском?", f"{sig.id}", f"{sig.instrument.replace('_', '/')}", f"{check['reason']}", f"{sig.risk_amount or 0:.2f}", f"{check['risk_eur']:.2f}", f"{check['overshoot']:.1f}", f"{check['lots']}", f"{n}"),
            {"inline_keyboard": [[
                {"text": t("✅ Да, рискнуть {0}€", f"{check['risk_eur']:.2f}"),
                 "callback_data": f"riskok:{sig.id}:{n}"},
                {"text": t("✖️ Отмена"), "callback_data": f"ignore:{sig.id}"},
            ]]},
        )

    lots = check["lots"]
    r = await mt5_svc.place_signal_orders(
        db, sig.instrument, sig.direction, lots,
        sig.entry, sig.stop_loss, sig.take_profit, n,
        price_precision(sig.instrument), f"{ORDER_TAG} #{sig.id}")
    if not r["ok"]:
        return t("❌ Ордер отклонён: {0}", f"{r.get('error', 'ошибка MT5')}"), None
    tps = ", ".join(str(t) for t in r["take_profits"])
    msg = (t("✅ Открыто по сигналу #{0}: {1} ×{2} по {3} лот {4}\nSL {5} · TP {6}", f"{sig.id}", f"{sig.direction}", f"{r['opened']}", f"{r['lots']}", f"{r['symbol']}", f"{sig.stop_loss}", f"{tps}"))
    if force_risk:
        msg += (t("\n⚠️ С повышенным риском ≈{0}€ (×{1}) — по вашему подтверждению.", f"{check['risk_eur']:.2f}", f"{check['overshoot']:.1f}"))
    if r["opened"] < r["requested"]:
        msg += (t("\n⚠️ Запрошено {0} ордеров, брокер принял только {1}: {2}", f"{r['requested']}", f"{r['opened']}", f"{r.get('error', 'причина не указана')}"))
    return msg, None


async def _handle_callback(cb: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        creds = get_credentials(db)
        cfg = get_app_config(db)
        token = creds["telegram_bot_token"]
        data = cb.get("data") or ""
        msg = cb.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))

        # чужой чат — молча подтверждаем и не исполняем
        if not chat_id or chat_id != str(cfg["telegram_chat_id"]):
            await answer_callback(token, cb["id"])
            return

        m = re.fullmatch(r"(trade|riskok|ignore):(\d+)(?::(\d+))?", data)
        if not m:
            await answer_callback(token, cb["id"])
            return
        action, sig_id = m.group(1), int(m.group(2))
        orders = int(m.group(3)) if m.group(3) else None

        import time as _time
        if _time.time() - (msg.get("date") or 0) > MAX_CALLBACK_AGE:
            await answer_callback(token, cb["id"], t("Сигнал устарел"))
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            return

        sig = db.get(Signal, sig_id)

        if action == "ignore":
            # «Пропустить» — решение пользователя, его надо ЗАПИСАТЬ: иначе
            # сигнал остаётся pending и его подхватит автотрейд/зеркало.
            # `accepted` тоже отменяем: первое нажатие могло лишь запросить
            # подтверждение превышения риска, ордера при этом ещё не было.
            if sig is not None and (sig.confirm_state or "") in ("pending", "accepted"):
                sig.confirm_state = "declined"
                db.commit()
            await answer_callback(token, cb["id"], t("Пропущен"))
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            await send_message(token, chat_id,
                               t("✖️ Сигнал #{0} пропущен — сделка НЕ открыта.", f"{sig_id}"))
            return

        if sig is None:
            await answer_callback(token, cb["id"])
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            await send_message(token, chat_id, t("❌ Сигнал #{0} не найден.", f"{sig_id}"))
            return

        state = sig.confirm_state or "not_required"
        if state in ("declined", "unconfirmed"):
            await answer_callback(token, cb["id"], t("Сигнал не подтверждён"))
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            await send_message(
                token, chat_id,
                t("⛔️ Сигнал #{0} уже ", f"{sig_id}")
                + (t("пропущен") if state == "declined" else t("просрочен"))
                + t(" — сделка не открыта."))
            return
        if state == "pending":
            deadline = sig.confirm_expires_at
            if deadline is not None:
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > deadline:
                    sig.confirm_state = "unconfirmed"
                    db.commit()
                    await answer_callback(token, cb["id"], t("Время истекло"))
                    await clear_buttons(token, chat_id, msg.get("message_id", 0))
                    await send_message(
                        token, chat_id,
                        t("⏰ Сигнал #{0}: время на подтверждение истекло — сделка не открыта.", f"{sig_id}"))
                    return
            # подтверждение фиксируем ДО отправки ордера: повторное нажатие
            # уже не пройдёт как «pending»
            sig.confirm_state = "accepted"
            db.commit()

        # riskok — второе нажатие: пользователь согласился на превышение риска
        force_risk = action == "riskok"
        await answer_callback(token, cb["id"],
                              t("Открываю…") if force_risk else t("Проверяю…"))
        text, keyboard = await _open_from_signal(db, sig, cfg, orders,
                                                 force_risk=force_risk)
        await clear_buttons(token, chat_id, msg.get("message_id", 0))
        await send_message(token, chat_id, text, reply_markup=keyboard)
    finally:
        db.close()


async def poll_forever() -> None:
    """Отдельная фоновая задача: long-poll 20с, реагирует на кнопки почти
    мгновенно и не трогает бюджет Twelve Data."""
    while True:
        try:
            db = SessionLocal()
            try:
                creds = get_credentials(db)
                token = creds["telegram_bot_token"]
                offset = _load_offset(db)
            finally:
                db.close()
            if not token:
                await asyncio.sleep(60)
                continue

            r = await get_updates(token, offset)
            updates = r.get("result") or []
            if not updates:
                continue
            new_offset = max(u["update_id"] for u in updates) + 1
            db = SessionLocal()
            try:
                _save_offset(db, new_offset)  # сначала подтверждаем — нет повторов
            finally:
                db.close()
            for u in updates:
                cb = u.get("callback_query")
                if cb:
                    with contextlib.suppress(Exception):
                        await _handle_callback(cb)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(10)  # сеть/Telegram упали — не крутим вхолостую
