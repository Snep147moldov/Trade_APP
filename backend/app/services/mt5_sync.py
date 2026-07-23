"""Полная синхронизация сайта с MT5: брокер — источник истины по деньгам.

Каждый тик (планировщик, ~60с):
  1) accountInformation -> баланс/эквити;
  2) открытые позиции -> плавающий P&L, по сигналам (комментарий Codnixy #id);
  3) history-deals за окно -> реальный закрытый P&L КАЖДОГО сигнала:
     profit + commission + swap всех сделок выхода (entry OUT), у которых
     positionId открывался ордером этого сигнала. Ордера ×2/×3 суммируются
     сами собой — у каждого свой positionId, все ведут к одному #id.

Итог пишется в Signal.mt5_pnl/mt5_volume/mt5_orders и в Setting "mt5_state"
(баланс, эквити, флоат, реальный P&L за сегодня/7 дней) — API и UI читают
кэш, не дёргая MetaApi на каждый запрос.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Setting, Signal
from . import mt5 as mt5_svc
from .runtime import get_credentials

STATE_KEY = "mt5_state"
SYNC_WINDOW_DAYS = 7
_SIG_RE = re.compile(r"#(\d+)")

_DEAL_TRADE_TYPES = ("DEAL_TYPE_BUY", "DEAL_TYPE_SELL")


def get_state(db: Session) -> dict[str, Any]:
    row = db.get(Setting, STATE_KEY)
    return dict(row.value) if row else {}


def _save_state(db: Session, state: dict[str, Any]) -> None:
    row = db.get(Setting, STATE_KEY)
    if row:
        row.value = state
    else:
        db.add(Setting(key=STATE_KEY, value=state))
    db.commit()


def _sig_id(comment: str) -> int | None:
    m = _SIG_RE.search(comment or "")
    return int(m.group(1)) if m else None


def _deal_ts(deal: dict) -> float:
    t = deal.get("time")
    if isinstance(t, str):
        try:
            return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


async def sync_tick(db: Session) -> None:
    creds = get_credentials(db)
    if not mt5_svc.is_configured(creds):
        return

    now = datetime.now(timezone.utc)
    state: dict[str, Any] = {"updated_at": now.isoformat(), "connected": False}

    info = await mt5_svc.account_information(db)
    if info.get("ok"):
        a = info["account"]
        state.update(connected=True, balance=a.get("balance"),
                     equity=a.get("equity"), margin=a.get("margin"),
                     free_margin=a.get("freeMargin"), currency=a.get("currency"))

    # открытые позиции: плавающий P&L, привязка к сигналам
    floating = 0.0
    by_signal_float: dict[str, float] = {}
    open_positions = 0
    pos = await mt5_svc.positions(db)
    if pos.get("ok"):
        open_positions = len(pos["positions"])
        for p in pos["positions"]:
            profit = float(p.get("profit") or 0.0)
            floating += profit
            sid = _sig_id(p.get("comment") or "")
            if sid is not None:
                key = str(sid)
                by_signal_float[key] = round(by_signal_float.get(key, 0.0) + profit, 2)
    state.update(floating=round(floating, 2), open_positions=open_positions,
                 floating_by_signal=by_signal_float)

    # история сделок: реальный P&L по сигналам + за сегодня/неделю
    start = (now - timedelta(days=SYNC_WINDOW_DAYS)).isoformat()
    hist = await mt5_svc.history_deals(db, start, now.isoformat())
    if hist.get("ok"):
        deals = [d for d in hist["deals"] if d.get("type") in _DEAL_TRADE_TYPES]
        # позиция -> сигнал: по комментарию сделки входа (или любой сделки)
        pos_to_sig: dict[str, int] = {}
        for d in deals:
            sid = _sig_id(d.get("comment") or d.get("brokerComment") or "")
            pid = str(d.get("positionId") or "")
            if sid is not None and pid and pid not in pos_to_sig:
                pos_to_sig[pid] = sid

        per_signal: dict[int, dict[str, float]] = {}
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_real = 0.0
        week_real = 0.0
        for d in deals:
            net = (float(d.get("profit") or 0.0) + float(d.get("commission") or 0.0)
                   + float(d.get("swap") or 0.0))
            entry = d.get("entryType")
            pid = str(d.get("positionId") or "")
            sid = pos_to_sig.get(pid)
            if entry == "DEAL_ENTRY_OUT":
                week_real += net
                if _deal_ts(d) >= today_start:
                    today_real += net
                if sid is not None:
                    agg = per_signal.setdefault(sid, {"pnl": 0.0, "volume": 0.0, "orders": 0})
                    agg["pnl"] += net
            elif entry == "DEAL_ENTRY_IN" and sid is not None:
                agg = per_signal.setdefault(sid, {"pnl": 0.0, "volume": 0.0, "orders": 0})
                agg["volume"] += float(d.get("volume") or 0.0)
                agg["orders"] += 1

        if per_signal:
            rows = db.scalars(select(Signal).where(
                Signal.id.in_(list(per_signal)))).all()
            for sig in rows:
                agg = per_signal[sig.id]
                if agg["orders"]:
                    sig.mt5_volume = round(agg["volume"], 2)
                    sig.mt5_orders = int(agg["orders"])
                # pnl появляется после первой сделки выхода; до тех пор None
                closed_pnl = round(agg["pnl"], 2)
                if closed_pnl != 0.0 or (sig.mt5_orders and str(sig.id) not in by_signal_float):
                    sig.mt5_pnl = closed_pnl
            db.commit()

        state.update(today_real=round(today_real, 2),
                     week_real=round(week_real, 2))

    _save_state(db, state)
