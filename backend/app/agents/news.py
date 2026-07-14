"""Scheduled AI analysis pipeline (runs 1-2x/day to keep token usage low).

Modeled on the multi-agent research pattern (bull/bear researcher debate ->
verdict), executed frugally in exactly three API calls per run:

  1. Haiku  — triage raw RSS headlines, keep the ~10 market movers
  2. Sonnet — bull-vs-bear debate over those headlines -> per-currency
              sentiment vector in [-1, 1] + written bull/bear cases
  3. Sonnet — directional bias in [-1, 1] for every watchlist pair

Results are stored in the news_analyses table; the deterministic engine reads
the *stored* vectors between runs — zero AI tokens per analysis request.
Every call is logged to api_usage with an estimated cost.
"""

import time
from typing import Any

import feedparser
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import HAIKU_MODEL, SONNET_MODEL
from ..models import NewsAnalysis
from ..services.runtime import log_usage

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"]

RSS_FEEDS = [
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_1.rss",
]


class TriagedHeadline(BaseModel):
    index: int = Field(description="index of the headline in the input list")
    relevant: bool = Field(description="true if it can move a G8 currency")
    impact: float = Field(description="expected market impact, 0 to 1")


class TriageResult(BaseModel):
    headlines: list[TriagedHeadline]


class CurrencySentiment(BaseModel):
    currency: str = Field(description="ISO code, one of USD EUR GBP JPY CHF AUD CAD NZD")
    sentiment: float = Field(description="-1 (very bearish) to +1 (very bullish)")
    rationale: str = Field(description="одно короткое предложение на русском")


class DebateResult(BaseModel):
    bull_case: str = Field(description="аргументы быков, 2-3 предложения на русском")
    bear_case: str = Field(description="аргументы медведей, 2-3 предложения на русском")
    sentiments: list[CurrencySentiment]
    summary: str = Field(description="итоговый вердикт, 2 предложения на русском")


class PairBias(BaseModel):
    pair: str = Field(description="instrument like EUR_USD, exactly as given")
    bias: float = Field(description="directional bias, -1 (strong sell) to +1 (strong buy)")
    confidence: float = Field(description="0 to 1")
    rationale: str = Field(description="одно короткое предложение на русском")


class PairBiasResult(BaseModel):
    pairs: list[PairBias]


def latest_analysis(db: Session) -> NewsAnalysis | None:
    return db.scalars(
        select(NewsAnalysis).order_by(NewsAnalysis.created_at.desc()).limit(1)
    ).first()


def analysis_to_dict(row: NewsAnalysis | None) -> dict[str, Any]:
    if row is None:
        return {
            "vector": {c: 0.0 for c in CURRENCIES},
            "rationales": {},
            "summary": "ИИ-анализ ещё не запускался — нейтральный фон.",
            "bull_case": "",
            "bear_case": "",
            "headlines": [],
            "pair_biases": {},
            "created_at": None,
        }
    return {
        "vector": row.vector,
        "rationales": row.rationales,
        "summary": row.summary,
        "bull_case": row.bull_case,
        "bear_case": row.bear_case,
        "headlines": row.headlines,
        "pair_biases": row.pair_biases,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def pair_sentiment(vector: dict[str, float], instrument: str) -> float:
    """Sentiment for BASE_QUOTE = sentiment(base) - sentiment(quote), clipped."""
    base, quote = instrument.split("_")
    val = vector.get(base, 0.0) - vector.get(quote, 0.0)
    return max(-1.0, min(1.0, val))


async def _fetch_headlines(limit: int = 30) -> list[str]:
    headlines: list[str] = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (codnixy-ai-trade)"}) as client:
        for url in RSS_FEEDS:
            try:
                r = await client.get(url)
                r.raise_for_status()
                feed = feedparser.parse(r.text)
                for entry in feed.entries[:20]:
                    title = getattr(entry, "title", "").strip()
                    if title:
                        headlines.append(title)
            except Exception:
                continue
    seen: set[str] = set()
    out = []
    for h in headlines:
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out[:limit]


async def _triage(client, headlines: list[str]) -> list[str]:
    numbered = "\n".join(f"{i}. {h}" for i, h in enumerate(headlines))
    resp = await client.messages.parse(
        model=HAIKU_MODEL,
        max_tokens=2000,
        system="You triage financial headlines for a forex trading system. "
               "Mark a headline relevant only if it could plausibly move a G8 currency "
               "(central banks, inflation, employment, GDP, geopolitics, risk sentiment).",
        messages=[{"role": "user", "content": f"Triage these headlines:\n{numbered}"}],
        output_format=TriageResult,
    )
    log_usage(HAIKU_MODEL, "triage", resp.usage.input_tokens, resp.usage.output_tokens)
    triaged = resp.parsed_output
    if triaged is None:
        return headlines[:10]
    ranked = sorted(
        (t for t in triaged.headlines if t.relevant and 0 <= t.index < len(headlines)),
        key=lambda t: t.impact,
        reverse=True,
    )
    return [headlines[t.index] for t in ranked[:10]]


async def _debate(client, headlines: list[str]) -> DebateResult | None:
    listed = "\n".join(f"- {h}" for h in headlines)
    resp = await client.messages.parse(
        model=SONNET_MODEL,
        max_tokens=3500,
        system="You are a macro FX research team running a structured bull-vs-bear "
               "debate. First argue the strongest bullish case for risk/major "
               "currencies, then the strongest bearish case, then settle the debate "
               "with a verdict: a sentiment score for each G8 currency "
               "(USD EUR GBP JPY CHF AUD CAD NZD) in [-1, 1]. Be conservative — most "
               "headlines warrant scores near 0. Include every one of the 8 currencies "
               "exactly once. Write bull_case, bear_case, rationale and summary fields "
               "in Russian.",
        messages=[{"role": "user", "content": f"Заголовки за последние часы:\n{listed}"}],
        output_format=DebateResult,
    )
    log_usage(SONNET_MODEL, "debate", resp.usage.input_tokens, resp.usage.output_tokens)
    return resp.parsed_output


async def _pair_biases(client, watchlist: list[str], vector: dict[str, float],
                       summary: str, memory_ctx: str = "") -> dict[str, dict[str, Any]]:
    if not watchlist:
        return {}
    ctx = ", ".join(f"{c}: {v:+.2f}" for c, v in vector.items())
    pairs = "\n".join(f"- {p}" for p in watchlist)
    resp = await client.messages.parse(
        model=SONNET_MODEL,
        max_tokens=3000,
        system="You are an FX strategist assisting a deterministic, formula-based "
               "signal engine. For each listed pair output a bounded directional "
               "bias grounded in the sentiment context. Be conservative — bias near 0 "
               "unless the evidence is clear. Your output is one capped input among "
               "many; you are not making trading decisions. Rationale in Russian. "
               "Accumulated lessons from the app's persistent memory are provided — "
               "use them to avoid repeating past mistakes.",
        messages=[{
            "role": "user",
            "content": f"Сентимент по валютам: {ctx}\nВердикт: {summary}\n\n"
                       f"Память (уроки прошлых сделок):\n{memory_ctx or '—'}\n\n"
                       f"Пары для оценки:\n{pairs}",
        }],
        output_format=PairBiasResult,
    )
    log_usage(SONNET_MODEL, "pair_bias", resp.usage.input_tokens, resp.usage.output_tokens)
    parsed = resp.parsed_output
    out: dict[str, dict[str, Any]] = {}
    if parsed:
        for p in parsed.pairs:
            key = p.pair.upper().replace("/", "_")
            if key in watchlist:
                bias = max(-1.0, min(1.0, p.bias)) * max(0.0, min(1.0, p.confidence))
                out[key] = {
                    "bias": round(bias, 3),
                    "confidence": round(max(0.0, min(1.0, p.confidence)), 2),
                    "rationale": p.rationale,
                }
    return out


async def run_pipeline(db: Session, anthropic_key: str, watchlist: list[str]) -> NewsAnalysis:
    """Full scheduled run. Raises on missing key; caller handles."""
    if not anthropic_key:
        raise RuntimeError("no anthropic key")

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        headlines = await _fetch_headlines()
        vector = {c: 0.0 for c in CURRENCIES}
        rationales: dict[str, str] = {}
        bull, bear = "", ""
        summary = "Новостей, способных сдвинуть рынок, не обнаружено."
        relevant: list[str] = []
        biases: dict[str, dict[str, Any]] = {}

        if headlines:
            relevant = await _triage(client, headlines)
            debate = await _debate(client, relevant) if relevant else None
            if debate:
                for s in debate.sentiments:
                    code = s.currency.upper()
                    if code in vector:
                        vector[code] = max(-1.0, min(1.0, s.sentiment))
                        rationales[code] = s.rationale
                bull, bear, summary = debate.bull_case, debate.bear_case, debate.summary
            from ..services import memory as ai_memory
            biases = await _pair_biases(client, watchlist, vector, summary,
                                        ai_memory.context_block(db))
    finally:
        await client.close()

    row = NewsAnalysis(
        vector=vector,
        rationales=rationales,
        summary=summary,
        bull_case=bull,
        bear_case=bear,
        headlines=relevant,
        pair_biases=biases,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
