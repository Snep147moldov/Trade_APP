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
from typing import Any

from ..database import SessionLocal
from ..models import Setting, Signal
from .runtime import get_app_config, get_credentials
from .telegram import answer_callback, clear_buttons, get_updates, send_message

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


async def _open_from_signal(db, sig: Signal, cfg: dict) -> str:
    """Кнопка «Купить»: открывает сделку(и) по сохранённым уровням сигнала."""
    from .candles import price_precision
    from . import mt5 as mt5_svc
    from .scheduler import autotrade_order_count

    creds = get_credentials(db)
    if not mt5_svc.is_configured(creds):
        return "❌ MT5 не подключён — откройте «Подключения» в приложении."
    if sig.status != "open":
        return f"⏸ Сигнал #{sig.id} уже закрыт ({sig.status}) — вход неактуален."

    # дедупликация: по этому сигналу уже есть позиция у брокера
    pos = await mt5_svc.positions(db)
    if pos.get("ok"):
        pat = re.compile(rf"#{sig.id}(\D|$)")
        if any(pat.search(p.get("comment") or "") for p in pos["positions"]):
            return f"ℹ️ По сигналу #{sig.id} позиция уже открыта."

    n = autotrade_order_count(cfg, (sig.confidence or 0) * 100)
    r = await mt5_svc.place_signal_orders(
        db, sig.instrument, sig.direction, cfg["autotrade_lots"],
        sig.entry, sig.stop_loss, sig.take_profit, n,
        price_precision(sig.instrument), f"Codnixy #{sig.id}")
    if not r["ok"]:
        return f"❌ Ордер отклонён: {r.get('error', 'ошибка MT5')}"
    tps = ", ".join(str(t) for t in r["take_profits"])
    return (f"✅ Открыто по сигналу #{sig.id}: {sig.direction} "
            f"×{r['opened']} по {r['lots']} лот {r['symbol']}\n"
            f"SL {sig.stop_loss} · TP {tps}")


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

        m = re.fullmatch(r"(trade|ignore):(\d+)", data)
        if not m:
            await answer_callback(token, cb["id"])
            return
        action, sig_id = m.group(1), int(m.group(2))

        import time as _time
        if _time.time() - (msg.get("date") or 0) > MAX_CALLBACK_AGE:
            await answer_callback(token, cb["id"], "Сигнал устарел")
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            return

        if action == "ignore":
            await answer_callback(token, cb["id"], "Пропущен")
            await clear_buttons(token, chat_id, msg.get("message_id", 0))
            await send_message(token, chat_id, f"✖️ Сигнал #{sig_id} пропущен.")
            return

        await answer_callback(token, cb["id"], "Открываю…")
        sig = db.get(Signal, sig_id)
        text = (f"❌ Сигнал #{sig_id} не найден." if sig is None
                else await _open_from_signal(db, sig, cfg))
        await clear_buttons(token, chat_id, msg.get("message_id", 0))
        await send_message(token, chat_id, text)
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
