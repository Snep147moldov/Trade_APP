"""Broker cash reconciliation from a persistent, account-scoped deal ledger.

Entry and exit commission/swap are included. A failed positions request never
means flat. Rolling API windows update unique tickets instead of replacing a
signal's lifetime P&L. Only tagged entry deals establish signal ownership.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import OUR_ORDER_TAGS
from ..models import BrokerDeal, Setting, Signal
from . import mt5 as mt5_svc
from .runtime import get_app_config, get_credentials
from .telegram import send_message

STATE_KEY = "mt5_state"
SYNC_WINDOW_DAYS = 7
BUCHAREST_TZ = ZoneInfo("Europe/Bucharest")
_SIG_RE = re.compile(r"(?:^|\s)(?:" + "|".join(map(re.escape, OUR_ORDER_TAGS))
                     + r")\s+(?:auto\s+)?#(\d+)(?!\d)")
_TRADE_TYPES = ("DEAL_TYPE_BUY", "DEAL_TYPE_SELL")
_OUT_TYPES = ("DEAL_ENTRY_OUT", "DEAL_ENTRY_OUT_BY")


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
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
        except ValueError:
            pass
    return 0.0


def _net(d: dict) -> float:
    return sum(float(d.get(k) or 0.) for k in ("profit", "commission", "swap", "fee"))


def _aggregate(deals: list[dict]) -> tuple[dict, dict]:
    """Unknown/mixed ownership or netting reversals cannot identify our P&L."""
    owners: dict[str, set] = {}
    for d in deals:
        if d.get("entryType") in ("DEAL_ENTRY_IN", "DEAL_ENTRY_INOUT"):
            pid = str(d.get("positionId") or "")
            sid = _sig_id(d.get("comment") or "") or _sig_id(d.get("brokerComment") or "")
            owners.setdefault(pid, set()).add(sid if d.get("entryType") == "DEAL_ENTRY_IN" else None)
    mapping = {pid: next(iter(sids)) for pid, sids in owners.items()
               if pid and len(sids) == 1 and None not in sids}
    result = {}
    for d in deals:
        sid = mapping.get(str(d.get("positionId") or ""))
        if sid is None:
            continue
        a = result.setdefault(sid, dict(pnl=0., volume=0., exit_volume=0.,
                                        orders=set(), last_exit=0., has_exit=False))
        a["pnl"] += _net(d)
        if d.get("entryType") == "DEAL_ENTRY_IN":
            a["volume"] += float(d.get("volume") or 0.)
            a["orders"].add(str(d.get("orderId") or d["id"]))
        elif d.get("entryType") in _OUT_TYPES:
            a["exit_volume"] += float(d.get("volume") or 0.)
            a["has_exit"] = True
            a["last_exit"] = max(a["last_exit"], _deal_ts(d))
    return result, mapping


def _finish_signal(sig: Signal, net: float, timestamp: float) -> None:
    # Legacy status names encode outcome sign, not proof of which order filled.
    sig.status = "hit_tp" if net > 0 else "hit_sl"
    sig.pnl_money = sig.mt5_pnl = round(net, 2)
    sig.resolved_at = datetime.fromtimestamp(timestamp, timezone.utc)
    if sig.risk_amount:
        sl_dist = abs((sig.entry or 0) - (sig.stop_loss or 0))
        if sl_dist > 0:
            from .candles import pip_size
            sig.pnl_pips = round(net / sig.risk_amount * sl_dist / pip_size(sig.instrument), 1)


async def sync_tick(db: Session) -> None:
    creds = get_credentials(db)
    if not mt5_svc.is_configured(creds):
        return
    account = creds["mt5_account_id"]
    now = datetime.now(timezone.utc)
    prev = get_state(db)
    if prev.get("ledger_account") != account:
        prev = {}  # broker identifiers and cursors belong to one account only
    state: dict[str, Any] = {**prev, "updated_at": now.isoformat(), "connected": False,
                             "ledger_account": account}
    info = await mt5_svc.account_information(db)
    if info.get("ok"):
        a = info["account"]
        state.update(connected=True, balance=a.get("balance"), equity=a.get("equity"),
                     margin=a.get("margin"), free_margin=a.get("freeMargin"), currency=a.get("currency"))

    pos = await mt5_svc.positions(db)
    state["positions_ok"] = bool(pos.get("ok"))
    start = now - timedelta(days=SYNC_WINDOW_DAYS)
    if prev.get("ledger_synced_at"):
        # A longer outage must not leave a hole between successful snapshots.
        cursor = datetime.fromisoformat(prev["ledger_synced_at"])
        start = min(start, cursor - timedelta(minutes=5))
    else:
        earliest = db.scalar(select(Signal.created_at).order_by(Signal.created_at).limit(1))
        if earliest:
            start = min(start, earliest.replace(tzinfo=earliest.tzinfo or timezone.utc) - timedelta(days=1))
    hist = await mt5_svc.history_deals(db, start.isoformat(), now.isoformat())
    state["history_ok"] = bool(hist.get("ok"))
    if hist.get("ok"):
        for d in hist["deals"]:
            if d.get("type") not in _TRADE_TYPES:
                continue
            ticket = str(d["id"])
            row = db.get(BrokerDeal, (account, ticket))
            if row:
                row.payload = d
            else:
                db.add(BrokerDeal(account_id=account, deal_id=ticket, payload=d))
        db.flush()
        state["ledger_synced_at"] = now.isoformat()
    deals = [row.payload for row in db.scalars(select(BrokerDeal).where(BrokerDeal.account_id == account))]
    per_signal, mapping = _aggregate(deals)

    live = set()
    curr_ids = []
    if pos.get("ok"):
        floating = 0.
        by_signal = {}
        for p in pos["positions"]:
            pid = str(p.get("id"))
            curr_ids.append(pid)
            profit = float(p.get("profit") or 0.)
            floating += profit
            sid = mapping.get(pid) or _sig_id(p.get("comment") or "")
            if sid is not None:
                live.add(sid)
                key = str(sid)
                by_signal[key] = round(by_signal.get(key, 0.) + profit, 2)
        state.update(floating=round(floating, 2), open_positions=len(curr_ids),
                     floating_by_signal=by_signal, position_ids=curr_ids)

    if hist.get("ok"):
        today = now.astimezone(BUCHAREST_TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        week = (now - timedelta(days=7)).timestamp()
        # Account cash flow includes entry fees and positions from other systems;
        # strategy P&L remains separately attributed in Signal and *_strategy.
        for label, cutoff in (("today", today), ("week", week)):
            recent = [d for d in deals if _deal_ts(d) >= cutoff]
            state[label + "_real"] = round(sum(_net(d) for d in recent), 2)
            state[label + "_strategy"] = round(sum(_net(d) for d in recent
                if str(d.get("positionId") or "") in mapping), 2)
        for sig in db.scalars(select(Signal).where(Signal.id.in_(list(per_signal)))):
            a = per_signal[sig.id]
            sig.mt5_orders = len(a["orders"])
            sig.mt5_volume = round(a["volume"], 8)
            sig.mt5_pnl = round(a["pnl"], 2) if a["has_exit"] else None
            complete = a["has_exit"] and a["last_exit"] > 0 and a["exit_volume"] >= a["volume"] - 1e-8
            if pos.get("ok") and sig.id not in live and complete:
                _finish_signal(sig, a["pnl"], a["last_exit"])
        db.commit()

        cfg = get_app_config(db)
        if cfg.get("telegram_enabled") and pos.get("ok"):
            for pid in set(prev.get("position_ids") or []) - set(curr_ids):
                if pid not in mapping:
                    continue
                pd = [d for d in deals if str(d.get("positionId") or "") == pid]
                if not any(d.get("entryType") in _OUT_TYPES for d in pd):
                    continue
                net = sum(_net(d) for d in pd)
                symbol = pd[-1].get("symbol") or "?"
                await send_message(creds["telegram_bot_token"], cfg["telegram_chat_id"],
                    f"MT5: позиция закрыта · {symbol} · сигнал #{mapping[pid]}\n"
                    f"Реальный результат с комиссиями: {net:+.2f}€")
    _save_state(db, state)
