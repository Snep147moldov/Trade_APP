"""Разговорный ИИ-ассистент и новостная аналитика по символу.

The assistant answers free-form questions ("почему двинулся EUR/USD?",
"что показывает RSI?", "какие риски у этой сделки?") by combining: live
technicals, detected chart patterns, stored news vectors, the economic
calendar, portfolio/risk state and the persistent AI memory. One Sonnet call
per message; usage is logged like every other AI purpose.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..config import SONNET_MODEL
from ..models import NewsAnalysis
from ..services import memory
from ..services.runtime import log_usage
from .news import _fetch_headlines, analysis_to_dict, latest_analysis
from ..i18n import answer_language_clause, t

MAX_HISTORY = 12


async def _instrument_context(db: Session, instrument: str, timeframe: str) -> str:
    from ..services.analysis import analyze
    from ..signals.patterns import detect

    try:
        a = await analyze(instrument, timeframe, db)
    except Exception:
        return t("(данные по {0} недоступны)", f"{instrument}")
    ind = a["indicators"]

    def f(key, digits=5):
        v = ind.get(key)
        return f"{v:.{digits}g}" if isinstance(v, (int, float)) else "—"

    pat = detect(a["candles"])
    pat_txt = "; ".join(
        f"{p['name']} ({p['direction']}, {p['status']})" for p in pat["patterns"][:4]
    ) or t("нет")
    zones = ", ".join(
        t("{0} {1} ({2} касаний)", f"{z['kind']}", f"{z['price']:.6g}", f"{z['touches']}")
        for z in pat["sr_zones"][:4]) or t("нет")

    return (
        t("Инструмент {0} {1}: цена {2}, направление движка {3} (оценка {4}, режим {5}).\nИндикаторы: RSI14 {6}, MACD hist {7}, ADX {8}, ATR14 {9}, %B {10}, Stoch K/D {11}/{12}, Hurst {13}, EMA20 {14} vs EMA50 {15}.\nУровни движка: вход {16}, SL {17}, TP {18}.\nПаттерны: {19}.\nЗоны S/R: {20}.", f"{instrument}", f"{timeframe}", f"{f('close')}", f"{a['direction']}", f"{a['score']:+.2f}", f"{a['regime']}", f"{f('rsi14', 3)}", f"{f('macd_hist')}", f"{f('adx14', 3)}", f"{f('atr14')}", f"{f('pct_b', 2)}", f"{f('stoch_k', 3)}", f"{f('stoch_d', 3)}", f"{f('hurst', 2)}", f"{f('ema20')}", f"{f('ema50')}", f"{a['levels']['entry']}", f"{a['levels']['stop_loss']}", f"{a['levels']['take_profit']}", f"{pat_txt}", f"{zones}")
    )


async def _shared_context(db: Session, instrument: str) -> str:
    from ..risk.monitor import portfolio_monitor
    from ..services.calendar import upcoming
    from ..services.journal import journal_stats
    from ..services.market import market_state
    from ..services.settings import get_settings

    news = analysis_to_dict(latest_analysis(db))
    vec = ", ".join(f"{c}: {v:+.2f}" for c, v in news["vector"].items())
    heads = "; ".join(news["headlines"][:6]) or t("нет")

    try:
        events = await upcoming(within_minutes=24 * 60, min_impact="medium")
        ev_txt = "; ".join(
            t("{0} {1} (важность {2})", f"{e['currency']}", f"{e['title']}", f"{e['impact']}")
            for e in events[:6]) or t("нет")
    except Exception:
        ev_txt = t("недоступен")

    try:
        risk = await portfolio_monitor(db)
        risk_txt = (t("открытых позиций {0}, плавающий P&L {1}€, дневной P&L {2}€, открытый риск {3}%", f"{len(risk['positions'])}", f"{risk['floating_eur']:+.2f}", f"{risk['limits']['daily_pnl']:+.2f}", f"{risk['limits']['open_risk_pct']:.1f}"))
        if risk["alerts"]:
            risk_txt += t(". Предупреждения: ") + "; ".join(
                a["title"] for a in risk["alerts"][:3])
    except Exception:
        risk_txt = t("недоступен")

    settings = get_settings(db)
    js = journal_stats(db, settings["account_equity"])
    stats_txt = (t("{0} закрытых, win rate {1}%, profit factor {2}, матожидание {3}€", f"{js['closed']}", f"{js['win_rate']}", f"{js['profit_factor']}", f"{js['expectancy']}")
                 if js["closed"] else t("сделок ещё нет"))

    ms = market_state()
    sessions = ", ".join(s["name"] for s in ms["sessions"] if s["active"]) or t("закрыт")

    return (
        t("Рынок: {0}; активные сессии: {1}.\nНовостной сентимент (ИИ, последний запуск): {2}.\nКлючевые заголовки: {3}.\nКалендарь на 24ч: {4}.\nПортфель: {5}.\nЖурнал: {6}.\nПамять (уроки и статистика):\n{7}", f"{'открыт' if ms['is_open'] else 'закрыт'}", f"{sessions}", f"{vec}", f"{heads}", f"{ev_txt}", f"{risk_txt}", f"{stats_txt}", f"{memory.context_block(db, instrument)}")
    )


async def chat(db: Session, anthropic_key: str, message: str,
               history: list[dict[str, str]], instrument: str = "",
               timeframe: str = "1h") -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    ctx_parts = [await _shared_context(db, instrument)]
    if instrument:
        ctx_parts.append(await _instrument_context(db, instrument, timeframe))
    context = "\n\n".join(ctx_parts)

    msgs: list[dict[str, str]] = []
    for h in history[-MAX_HISTORY:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:4000]})
    msgs.append({"role": "user", "content": message[:4000]})

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1400,
            system=(
                t("Ты — торговый аналитик-ассистент приложения FX Navigator. Отвечай по-русски, кратко и предметно, опираясь ТОЛЬКО на данные из контекста ниже (технику, новости, календарь, портфель, память). Объясняй причины движений через комбинацию факторов; если данных нет — честно скажи. Указывай риски. Не давай гарантий и не выдумывай цифры. Это поддержка решений, не финансовый совет — напоминай об этом только при прямых просьбах о рекомендации.\n\n=== КОНТЕКСТ ===\n{0}", f"{context}")
                + answer_language_clause()
            ),
            messages=msgs,
        )
        log_usage(SONNET_MODEL, "chat", resp.usage.input_tokens, resp.usage.output_tokens)
        reply = "".join(b.text for b in resp.content if b.type == "text")
    finally:
        await client.close()

    return {"reply": reply, "instrument": instrument, "timeframe": timeframe}


# ---------------------------------------------------------------------------
# News intelligence for one symbol: summarize, rank, explain impact
# ---------------------------------------------------------------------------

async def symbol_news(db: Session, anthropic_key: str, instrument: str) -> dict[str, Any]:
    from anthropic import AsyncAnthropic
    from pydantic import BaseModel, Field

    class NewsItem(BaseModel):
        headline: str
        sentiment: str = Field(description="positive | neutral | negative")
        impact: float = Field(description=t("ожидаемое влияние на инструмент, 0..1"))
        why: str = Field(description=t("почему это важно для инструмента, 1 предложение, русский"))

    class NewsIntel(BaseModel):
        summary: str = Field(description=t("сводка по инструменту, 2-3 предложения, русский"))
        overall_sentiment: str = Field(description="positive | neutral | negative")
        items: list[NewsItem] = Field(description=t("только релевантные, отсортированы по важности"))

    headlines = await _fetch_headlines(limit=30)
    if not headlines:
        return {"summary": t("Свежих заголовков не найдено."), "overall_sentiment": "neutral",
                "items": [], "instrument": instrument}

    mem_ctx = memory.context_block(db, instrument, max_items=4)
    listed = "\n".join(f"- {h}" for h in headlines)

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.parse(
            model=SONNET_MODEL,
            max_tokens=2500,
            system=(t("Ты — новостной аналитик. Для указанного инструмента отбери из заголовков только релевантные, оцени тональность и влияние, объясни почему каждая новость важна. Ранжируй по важности. Русский язык, без воды. Учитывай накопленные уроки из памяти.") + answer_language_clause()),
            messages=[{"role": "user", "content":
                       t("Инструмент: {0}\n\nЗаголовки:\n{1}\n\nПамять:\n{2}", f"{instrument.replace('_', '/')}", f"{listed}", f"{mem_ctx}")}],
            output_format=NewsIntel,
        )
        log_usage(SONNET_MODEL, "news_intel",
                  resp.usage.input_tokens, resp.usage.output_tokens)
        parsed = resp.parsed_output
    finally:
        await client.close()

    if not parsed:
        return {"summary": t("Не удалось разобрать новости."), "overall_sentiment": "neutral",
                "items": [], "instrument": instrument}

    out = parsed.model_dump()
    out["instrument"] = instrument
    # remember notable one-sided news pressure as a short-lived observation
    if out["items"] and out["overall_sentiment"] != "neutral":
        memory.add_memory(
            db, "regime", t("Новостной фон {0}", f"{instrument}"),
            f"{instrument}: {out['summary']}",
            instrument=instrument, importance=0.4, tags=["news"])
    # attach to the latest analysis row so the dashboard can show it
    row = latest_analysis(db)
    if row is not None:
        items = list(row.news_items or [])
        items = [i for i in items if i.get("instrument") != instrument]
        items.append({"instrument": instrument, "summary": out["summary"],
                      "overall_sentiment": out["overall_sentiment"],
                      "items": out["items"][:8]})
        row.news_items = items
        db.commit()
    return out
