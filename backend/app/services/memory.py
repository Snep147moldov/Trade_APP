"""ИИ-память: постоянная база знаний, накапливающая опыт между сессиями.

Deterministic layer (free, always on):
  - trade_review per closed signal: outcome in R, which factors agreed;
  - pattern_stat per factor: rolling hit-rate of every confluence factor;
  - regime stat: win rate by market regime (trending/ranging at entry).

AI layer (scheduled, cheap): consolidate() turns recent reviews + journal
stats into short "lessons" via Sonnet. Lessons, stats and user style are
injected into every AI prompt (news pipeline, assistant chat, journal review)
through context_block() — so the system's advice improves with history.
"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SONNET_MODEL
from ..models import AiMemory, Signal
from .runtime import log_usage

FACTORS = ("trend", "tsmom", "kama_er", "macd", "rsi", "stoch",
           "bollinger", "roc", "ai_news", "ai_prediction")
ALIGN_THRESHOLD = 0.15
CONSOLIDATE_EVERY = 10  # new closed trades between AI consolidations


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_memory(db: Session, kind: str, title: str, content: str,
               instrument: str = "", timeframe: str = "", tags: list | None = None,
               importance: float = 0.5, meta: dict | None = None) -> AiMemory:
    row = AiMemory(kind=kind, title=title[:200], content=content,
                   instrument=instrument, timeframe=timeframe,
                   tags=tags or [], importance=importance, meta=meta or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _singleton(db: Session, kind: str, key_title: str) -> AiMemory | None:
    return db.scalars(
        select(AiMemory).where(AiMemory.kind == kind, AiMemory.title == key_title,
                               AiMemory.archived == 0)
    ).first()


def _upsert_stat(db: Session, kind: str, title: str, update) -> None:
    row = _singleton(db, kind, title)
    if row is None:
        row = AiMemory(kind=kind, title=title, content="", importance=0.6,
                       tags=[], meta={})
        db.add(row)
    meta = dict(row.meta or {})
    row.meta = update(meta)
    row.updated_at = utcnow()
    db.commit()


# ---------------------------------------------------------------------------
# Deterministic learning hooks
# ---------------------------------------------------------------------------

def record_trade_close(db: Session, sig: Signal) -> None:
    """Called for every resolved signal: writes a review + updates factor and
    regime statistics."""
    win = (sig.pnl_money or 0.0) > 0
    side = 1.0 if sig.direction == "BUY" else -1.0
    risk_dist = abs(sig.entry - sig.stop_loss)
    comp: dict[str, float] = sig.components or {}

    aligned = [f for f in FACTORS
               if abs(comp.get(f, 0.0)) >= ALIGN_THRESHOLD
               and comp.get(f, 0.0) * side > 0]
    against = [f for f in FACTORS
               if abs(comp.get(f, 0.0)) >= ALIGN_THRESHOLD
               and comp.get(f, 0.0) * side < 0]

    r_result = 0.0
    if risk_dist > 0 and sig.risk_amount:
        r_result = (sig.pnl_money or 0.0) / sig.risk_amount

    content = (
        f"{sig.instrument} {sig.timeframe} {sig.direction}: {sig.status}, "
        f"{(sig.pnl_money or 0):+.2f}€ ({r_result:+.2f}R). "
        f"Оценка {sig.score:+.2f}, уверенность {sig.confidence:.2f}. "
        f"Факторы ЗА: {', '.join(aligned) or '—'}. "
        f"Факторы ПРОТИВ: {', '.join(against) or '—'}."
        + (" Частичная фиксация сработала." if sig.partial_taken else "")
        + (" Стоп был переведён в безубыток." if sig.be_moved else "")
    )
    add_memory(db, "trade_review",
               f"Сделка #{sig.id} {sig.instrument} {sig.direction} → {sig.status}",
               content, instrument=sig.instrument, timeframe=sig.timeframe,
               tags=["win" if win else "loss", sig.status],
               importance=0.35, meta={"signal_id": sig.id, "r": round(r_result, 2)})

    # factor hit-rates: does a factor's agreement correlate with wins?
    def upd_factor(name: str):
        def _apply(meta: dict) -> dict:
            wins = int(meta.get("wins", 0))
            total = int(meta.get("total", 0))
            return {"wins": wins + (1 if win else 0), "total": total + 1}
        return _apply

    for f in aligned:
        _upsert_stat(db, "pattern_stat", f"factor:{f}", upd_factor(f))

    # regime stat (trending vs ranging at entry, approximated by score makeup)
    regime = "ranging" if abs(comp.get("bollinger", 0.0)) > abs(comp.get("trend", 0.0)) \
        else "trending"
    _upsert_stat(db, "regime", f"regime:{regime}", upd_factor(regime))

    # refresh the compact stat contents shown to the AI
    _refresh_stat_contents(db)
    invalidate_multiplier_cache()  # новый исход — веса пересчитаются


def _refresh_stat_contents(db: Session) -> None:
    rows = db.scalars(select(AiMemory).where(
        AiMemory.kind.in_(("pattern_stat", "regime")), AiMemory.archived == 0)).all()
    for row in rows:
        meta = row.meta or {}
        total = int(meta.get("total", 0))
        if total:
            wr = int(meta.get("wins", 0)) / total * 100
            row.content = f"{row.title}: {total} сделок, win rate {wr:.0f}%"
    db.commit()


def update_user_style(db: Session, settings: dict[str, Any]) -> None:
    def _apply(meta: dict) -> dict:
        return {**meta, "risk_per_trade_pct": settings["risk_per_trade_pct"],
                "risk_reward": settings["risk_reward"],
                "sizing_mode": settings["sizing_mode"],
                "ai_weight": settings["ai_weight"]}
    _upsert_stat(db, "user_style", "user:style", _apply)
    row = _singleton(db, "user_style", "user:style")
    if row:
        m = row.meta or {}
        row.content = (
            f"Стиль пользователя: риск {m.get('risk_per_trade_pct')}% на сделку, "
            f"R:R {m.get('risk_reward')}, сайзинг {m.get('sizing_mode')}, "
            f"вес ИИ {m.get('ai_weight')}"
        )
        db.commit()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def search(db: Session, instrument: str = "", kinds: tuple[str, ...] = (),
           limit: int = 12) -> list[AiMemory]:
    q = select(AiMemory).where(AiMemory.archived == 0)
    if kinds:
        q = q.where(AiMemory.kind.in_(kinds))
    rows = db.scalars(q.order_by(AiMemory.importance.desc(),
                                 AiMemory.created_at.desc()).limit(200)).all()
    if instrument:
        rows.sort(key=lambda r: (r.instrument != instrument, -r.importance))
    return rows[:limit]


def context_block(db: Session, instrument: str = "", max_items: int = 10) -> str:
    """Compact Russian knowledge block injected into AI prompts."""
    lessons = search(db, instrument, ("lesson", "journal_insight"), 4)
    stats = search(db, "", ("pattern_stat", "regime"), 5)
    style = search(db, "", ("user_style",), 1)
    reviews = search(db, instrument, ("trade_review",), 3)

    lines: list[str] = []
    for r in lessons[:max_items]:
        lines.append(f"[урок] {r.content}")
    for r in stats:
        if r.content:
            lines.append(f"[статистика] {r.content}")
    for r in style:
        lines.append(f"[стиль] {r.content}")
    for r in reviews:
        lines.append(f"[недавняя сделка] {r.content}")
    if not lines:
        return "Память пока пуста — накопленных уроков нет."
    return "\n".join(lines[:max_items + 4])


_MULT_CACHE: dict[str, Any] = {"ts": 0.0, "mults": None}
_MULT_TTL = 60
_MULT_MIN_TRADES = 10   # ниже — статистика фактора шумовая, вес не трогаем
_MULT_MAX_TILT = 0.15   # максимум ±15% к весу фактора


def factor_multipliers(db: Session) -> dict[str, float]:
    """Опыт -> веса: факторы, которые исторически чаще совпадали с прибыльными
    сделками, получают чуть больший вес (и наоборот). Ограничено ±15%,
    детерминировано, кэш 60с. Это главный контур «память улучшает будущие
    сделки» помимо ИИ-промптов."""
    import time as _time

    now = _time.time()
    if _MULT_CACHE["mults"] is not None and now - _MULT_CACHE["ts"] < _MULT_TTL:
        return _MULT_CACHE["mults"]

    mults = {f: 1.0 for f in FACTORS}
    rows = db.scalars(select(AiMemory).where(
        AiMemory.kind == "pattern_stat", AiMemory.archived == 0)).all()
    for r in rows:
        if not r.title.startswith("factor:"):
            continue
        name = r.title.removeprefix("factor:")
        meta = r.meta or {}
        total = int(meta.get("total", 0))
        if name in mults and total >= _MULT_MIN_TRADES:
            wr = int(meta.get("wins", 0)) / total
            tilt = max(-1.0, min(1.0, (wr - 0.5) * 2.0))  # [-1..1]
            mults[name] = 1.0 + tilt * _MULT_MAX_TILT
    _MULT_CACHE.update(ts=now, mults=mults)
    return mults


def invalidate_multiplier_cache() -> None:
    _MULT_CACHE["mults"] = None


def memory_to_dict(r: AiMemory) -> dict[str, Any]:
    return {
        "id": r.id, "kind": r.kind, "instrument": r.instrument,
        "timeframe": r.timeframe, "title": r.title, "content": r.content,
        "tags": r.tags, "importance": r.importance, "meta": r.meta,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------------------
# AI consolidation: reviews + stats -> short reusable lessons
# ---------------------------------------------------------------------------

def _consolidation_due(db: Session) -> bool:
    state = _singleton(db, "user_style", "memory:consolidation")
    last_id = int((state.meta or {}).get("last_signal_id", 0)) if state else 0
    newest = db.scalars(select(Signal).where(
        Signal.status.in_(("hit_tp", "hit_sl", "expired"))
    ).order_by(Signal.id.desc()).limit(1)).first()
    if not newest:
        return False
    count = db.scalars(select(Signal.id).where(
        Signal.id > last_id, Signal.status.in_(("hit_tp", "hit_sl", "expired"))
    )).all()
    return len(count) >= CONSOLIDATE_EVERY


async def consolidate(db: Session, anthropic_key: str) -> list[AiMemory]:
    """Sonnet distills recent trade reviews into <=3 short lessons."""
    if not anthropic_key or not _consolidation_due(db):
        return []
    from anthropic import AsyncAnthropic
    from pydantic import BaseModel, Field

    class Lesson(BaseModel):
        title: str = Field(description="короткий заголовок урока, русский")
        content: str = Field(description="1-2 предложения: что работает/не работает и почему")
        importance: float = Field(description="0..1")

    class Lessons(BaseModel):
        lessons: list[Lesson]

    reviews = search(db, "", ("trade_review",), 20)
    stats = search(db, "", ("pattern_stat", "regime"), 8)
    old_lessons = search(db, "", ("lesson",), 5)
    corpus = "\n".join(f"- {r.content}" for r in reviews)
    stat_txt = "\n".join(f"- {r.content}" for r in stats if r.content)
    known = "\n".join(f"- {r.content}" for r in old_lessons)

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.parse(
            model=SONNET_MODEL,
            max_tokens=1200,
            system="Ты — аналитик торгового журнала. Из разборов сделок и статистики "
                   "выведи максимум 3 НОВЫХ коротких урока (не повторяй уже известные). "
                   "Урок = конкретное наблюдение, применимое к будущим сделкам. "
                   "Пиши по-русски, без воды.",
            messages=[{"role": "user", "content":
                       f"Разборы сделок:\n{corpus}\n\nСтатистика:\n{stat_txt}\n\n"
                       f"Уже известные уроки:\n{known or '—'}"}],
            output_format=Lessons,
        )
        log_usage(SONNET_MODEL, "memory", resp.usage.input_tokens, resp.usage.output_tokens)
        parsed = resp.parsed_output
    finally:
        await client.close()

    out: list[AiMemory] = []
    if parsed:
        for l in parsed.lessons[:3]:
            out.append(add_memory(
                db, "lesson", l.title, l.content,
                importance=min(max(l.importance, 0.3), 0.95), tags=["auto"]))

    newest = db.scalars(select(Signal).order_by(Signal.id.desc()).limit(1)).first()
    def _apply(meta: dict) -> dict:
        return {**meta, "last_signal_id": newest.id if newest else 0,
                "last_run": utcnow().isoformat()}
    _upsert_stat(db, "user_style", "memory:consolidation", _apply)
    return out


def prune(db: Session, keep_reviews: int = 200) -> None:
    """Trade reviews are plentiful — keep the newest N, archive the rest."""
    rows = db.scalars(select(AiMemory).where(
        AiMemory.kind == "trade_review", AiMemory.archived == 0
    ).order_by(AiMemory.created_at.desc())).all()
    for r in rows[keep_reviews:]:
        r.archived = 1
    db.commit()


def dump_all(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.scalars(select(AiMemory).where(AiMemory.archived == 0)
                      .order_by(AiMemory.importance.desc(),
                                AiMemory.created_at.desc()).limit(limit)).all()
    return [memory_to_dict(r) for r in rows]


def export_json(db: Session) -> str:
    return json.dumps(dump_all(db, 500), ensure_ascii=False, indent=1)
