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


async def send_message(token: str, chat_id: str, text: str) -> dict[str, Any]:
    if not token or not chat_id:
        return {"ok": False, "error": "не заданы токен бота или chat_id"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": data.get("description", "ошибка Telegram API")}
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}"}


def format_signal(analysis: dict[str, Any], signal_id: int) -> str:
    d = analysis["direction"]
    arrow = "📈" if d == "BUY" else "📉"
    side = "ПОКУПКА" if d == "BUY" else "ПРОДАЖА"
    lv, risk = analysis["levels"], analysis["risk"]
    pair = analysis["instrument"].replace("_", "/")
    return (
        f"{arrow} <b>Codnixy AI Trade — сигнал #{signal_id}</b>\n"
        f"<b>{pair}</b> · {analysis['timeframe']} · <b>{side}</b>\n\n"
        f"Вход: <code>{lv['entry']}</code>\n"
        f"Стоп-лосс: <code>{lv['stop_loss']}</code> ({risk['sl_pips']} п.)\n"
        f"Тейк-профит: <code>{lv['take_profit']}</code> ({risk['tp_pips']} п.)\n"
        f"Риск/прибыль: 1:{analysis['risk_reward']}\n\n"
        f"Объём: {risk['units']:,} ед. · риск {risk['risk_amount']}€\n"
        f"Потенциальная прибыль: {risk['potential_profit']}€\n"
        f"Оценка: {analysis['score']:+.2f} · уверенность {int(analysis['confidence'] * 100)}%\n\n"
        f"<i>Поддержка решений, не финансовый совет.</i>"
    ).replace(",", " ")


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
