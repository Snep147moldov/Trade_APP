"""Telegram notifications: signals and outcomes go to a channel/chat.

The bot token and chat id are configured in the app UI. For a channel the bot
must be an admin; chat_id is either "@channelname" or a numeric -100... id.
"""

from typing import Any

import httpx


async def detect_chat_id(token: str) -> dict[str, Any]:
    """getUpdates -> chat id of the latest private message to the bot. The
    user must have messaged the bot at least once (bots can't start chats)."""
    if not token:
        return {"ok": False, "error": "не задан токен бота"}
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params={"limit": 50})
            data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": data.get("description", "ошибка Telegram API")}
        for upd in reversed(data.get("result", [])):
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat") or {}
            if chat.get("id"):
                return {"ok": True, "chat_id": str(chat["id"]),
                        "title": chat.get("title") or chat.get("username")
                        or chat.get("first_name") or ""}
        return {"ok": False,
                "error": "нет сообщений — напишите боту что-нибудь и повторите"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}"}


async def _call(token: str, method: str, payload: dict,
                timeout: float = 15) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": data.get("description", "ошибка Telegram API")}
        return {"ok": True, "result": data.get("result")}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}"}


def signal_keyboard(signal_id: int, recommended: int = 1,
                    max_orders: int = 3) -> dict[str, Any]:
    """Inline-кнопки: выбор числа ордеров (звёздочка = рекомендация движка)
    + «Пропустить»."""
    max_orders = max(max_orders, recommended, 1)
    row = []
    for n in range(1, min(max_orders, 5) + 1):
        star = "⭐ " if n == recommended else ""
        row.append({"text": f"{star}Купить ×{n}",
                    "callback_data": f"trade:{signal_id}:{n}"})
    return {"inline_keyboard": [
        row,
        [{"text": "✖️ Пропустить", "callback_data": f"ignore:{signal_id}"}],
    ]}


async def send_message(token: str, chat_id: str, text: str,
                       reply_markup: dict | None = None) -> dict[str, Any]:
    if not token or not chat_id:
        return {"ok": False, "error": "не заданы токен бота или chat_id"}
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await _call(token, "sendMessage", payload)


async def get_updates(token: str, offset: int, timeout: int = 20) -> dict[str, Any]:
    """Long-poll: callback-кнопки и сообщения; offset подтверждает обработанные."""
    return await _call(token, "getUpdates", {
        "offset": offset, "timeout": timeout,
        "allowed_updates": ["callback_query"],
    }, timeout=timeout + 10)


async def answer_callback(token: str, callback_id: str, text: str = "") -> dict[str, Any]:
    return await _call(token, "answerCallbackQuery",
                       {"callback_query_id": callback_id, "text": text[:200]})


async def clear_buttons(token: str, chat_id: str | int, message_id: int) -> dict[str, Any]:
    return await _call(token, "editMessageReplyMarkup", {
        "chat_id": chat_id, "message_id": message_id,
        "reply_markup": {"inline_keyboard": []},
    })


def format_signal(analysis: dict[str, Any], signal_id: int,
                  recommended_orders: int = 1) -> str:
    d = analysis["direction"]
    arrow = "📈" if d == "BUY" else "📉"
    side = "ПОКУПКА" if d == "BUY" else "ПРОДАЖА"
    lv, risk = analysis["levels"], analysis["risk"]
    pair = analysis["instrument"].replace("_", "/")
    units = f"{risk['units']:,}".replace(",", " ")
    return (
        f"{arrow} <b>Codnixy AI Trade — сигнал #{signal_id}</b>\n"
        f"<b>{pair}</b> · {analysis['timeframe']} · <b>{side}</b>\n\n"
        f"Вход: <code>{lv['entry']}</code>\n"
        f"Стоп-лосс: <code>{lv['stop_loss']}</code> ({risk['sl_pips']} п.)\n"
        f"Тейк-профит: <code>{lv['take_profit']}</code> ({risk['tp_pips']} п.)\n"
        f"Риск/прибыль: 1:{analysis['risk_reward']}\n\n"
        f"Объём: {units} ед. · риск {risk['risk_amount']}€\n"
        f"Потенциальная прибыль: {risk['potential_profit']}€\n"
        f"Оценка: {analysis['score']:+.2f} · уверенность {int(analysis['confidence'] * 100)}%\n"
        + (f"Рекомендуемое число ордеров: <b>{recommended_orders}</b> "
           f"(тейки ступенями: +1R, цель, цель×1.5)\n" if recommended_orders > 1
           else "")
        + "\n<i>Поддержка решений, не финансовый совет.</i>"
    )


def format_outcome(sig) -> str:
    pair = sig.instrument.replace("_", "/")
    pnl_p = sig.pnl_pips or 0
    pnl_m = sig.pnl_money or 0
    if sig.status == "hit_tp":
        head = f"✅ Сигнал #{sig.id} достиг цели"
    elif sig.status == "hit_sl":
        head = f"🛑 Сигнал #{sig.id} закрыт по стопу"
    else:
        head = f"⏳ Сигнал #{sig.id} истёк"
    return (
        f"<b>{head}</b>\n"
        f"{pair} · {sig.timeframe} · {'ПОКУПКА' if sig.direction == 'BUY' else 'ПРОДАЖА'}\n"
        f"Результат: {pnl_p:+.1f} п. · {pnl_m:+.2f}€"
        + ("\nЧастичная фиксация была выполнена ранее." if getattr(sig, "partial_taken", 0) else "")
    )
