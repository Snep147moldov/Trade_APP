#!/usr/bin/env python3
"""Read-only export of the trading history for offline analysis.

Standard library only (sqlite3 + json) so it runs on the VPS, inside the
backend container, or on a bare host — no venv, no pip install.

Never touches the database: opens it read-only and writes a separate file.
API keys, passwords and tokens are redacted before anything is written.

    python3 export_trades.py [path/to/forex.db] [-o out.json]
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

CLOSED = ("hit_tp", "hit_sl", "expired")
SECRET_HINTS = ("key", "token", "password", "secret")


def connect_ro(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        sys.exit(f"database not found: {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def columns(con, table: str) -> set:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def table_exists(con, table: str) -> bool:
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def redact(value):
    """Settings rows carry live credentials — strip them, keep the shape."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(h in k.lower() for h in SECRET_HINTS):
                out[k] = f"<redacted:{'set' if v else 'empty'}>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def pct(a, b):
    return round(a / b * 100, 1) if b else None


def hour_of(ts: str):
    try:
        return datetime.fromisoformat(ts).hour
    except (ValueError, TypeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default="forex.db")
    ap.add_argument("-o", "--out", default="trades_export.json")
    args = ap.parse_args()

    con = connect_ro(args.db)
    cols = columns(con, "signals")
    has = lambda c: c in cols  # noqa: E731

    signals = [dict(r) for r in con.execute(
        "SELECT * FROM signals ORDER BY created_at")]
    closed = [s for s in signals if s["status"] in CLOSED]

    rep = {"db": os.path.abspath(args.db),
           "exported_at": datetime.now(timezone.utc).isoformat(),
           "schema_columns": sorted(cols), "counts": {}, "findings": {}}

    # ---------------------------------------------------------------- overview
    rep["counts"] = {
        "signals_total": len(signals),
        "closed": len(closed),
        "open": sum(1 for s in signals if s["status"] == "open"),
        "first_created": signals[0]["created_at"] if signals else None,
        "last_created": signals[-1]["created_at"] if signals else None,
    }
    by_status = defaultdict(int)
    for s in signals:
        by_status[s["status"]] += 1
    rep["counts"]["by_status"] = dict(by_status)

    wins = [s for s in closed if (s["pnl_money"] or 0) > 0]
    losses = [s for s in closed if (s["pnl_money"] or 0) < 0]
    zeros = [s for s in closed if (s["pnl_money"] or 0) == 0]
    rep["findings"]["win_rate"] = {
        "wins": len(wins), "losses": len(losses),
        "exactly_zero_pnl": len(zeros),
        "win_rate_pct_all_closed": pct(len(wins), len(closed)),
        "win_rate_pct_excluding_zeros": pct(len(wins), len(closed) - len(zeros)),
        "breakeven_needed_at_rr_1_8_pct": 35.7,
    }

    # ------------------------------------- the 0.00 EUR mystery: was risk zero?
    zero_detail = defaultdict(int)
    for s in zeros:
        ra = s.get("risk_amount")
        units = s.get("units")
        if not ra:
            zero_detail["risk_amount_is_zero"] += 1
        elif not units:
            zero_detail["units_is_zero"] += 1
        else:
            zero_detail["risk_ok_so_exit_equals_entry"] += 1
    rep["findings"]["zero_pnl_causes"] = dict(zero_detail)
    risk_amounts = [s.get("risk_amount") or 0 for s in closed]
    if risk_amounts:
        srt = sorted(risk_amounts)
        rep["findings"]["risk_amount"] = {
            "min": srt[0], "median": srt[len(srt) // 2], "max": srt[-1],
            "count_zero": sum(1 for r in risk_amounts if r == 0),
        }

    # ------------------------------------------- realised R (money-based, safe)
    rs = []
    for s in closed:
        ra = s.get("risk_amount") or 0
        if ra:
            rs.append(round((s["pnl_money"] or 0) / ra, 3))
    if rs:
        srt = sorted(rs)
        rep["findings"]["realised_R"] = {
            "n": len(rs), "mean": round(sum(rs) / len(rs), 3),
            "min": srt[0], "p25": srt[len(srt) // 4],
            "median": srt[len(srt) // 2], "p75": srt[3 * len(srt) // 4],
            "max": srt[-1],
            "histogram": _hist(rs),
        }

    # ------------------------------- app-tracked money vs what the broker paid
    app_money = sum(s["pnl_money"] or 0 for s in closed)
    if has("mt5_pnl"):
        with_mt5 = [s for s in closed if s.get("mt5_pnl") is not None]
        rep["findings"]["app_vs_broker"] = {
            "signals_with_broker_pnl": len(with_mt5),
            "app_tracked_total_eur": round(app_money, 2),
            "broker_total_eur": round(sum(s["mt5_pnl"] for s in with_mt5), 2),
            "broker_lots_total": round(
                sum(s.get("mt5_volume") or 0 for s in with_mt5), 2),
            "broker_orders_total": sum(s.get("mt5_orders") or 0 for s in with_mt5),
            "note": "large divergence => app sizing and broker lots are decoupled",
        }
    else:
        rep["findings"]["app_vs_broker"] = {
            "app_tracked_total_eur": round(app_money, 2),
            "note": "mt5_* columns absent — older schema",
        }

    # ------------------------------------------------ breakdowns that matter
    def group(keyfn, label):
        g = defaultdict(lambda: {"n": 0, "wins": 0, "money": 0.0, "broker": 0.0})
        for s in closed:
            k = keyfn(s)
            if k is None:
                continue
            b = g[k]
            b["n"] += 1
            b["wins"] += 1 if (s["pnl_money"] or 0) > 0 else 0
            b["money"] += s["pnl_money"] or 0
            b["broker"] += s.get("mt5_pnl") or 0
        return {str(k): {"n": v["n"], "wins": v["wins"],
                         "win_rate_pct": pct(v["wins"], v["n"]),
                         "money_eur": round(v["money"], 2),
                         "broker_eur": round(v["broker"], 2)}
                for k, v in sorted(g.items(), key=lambda kv: -kv[1]["n"])}

    rep["by_instrument"] = group(lambda s: s["instrument"], "instrument")
    rep["by_timeframe"] = group(lambda s: s["timeframe"], "timeframe")
    rep["by_direction"] = group(lambda s: s["direction"], "direction")
    rep["by_hour_utc"] = group(lambda s: hour_of(s["created_at"]), "hour")
    if has("confirm_state"):
        rep["by_confirm_state"] = group(lambda s: s.get("confirm_state"), "confirm")

    # ------------------------------- does the engine's own score predict wins?
    buckets = defaultdict(lambda: {"n": 0, "wins": 0})
    for s in closed:
        sc = abs(s.get("score") or 0)
        b = buckets[f"{int(sc * 10) / 10:.1f}"]
        b["n"] += 1
        b["wins"] += 1 if (s["pnl_money"] or 0) > 0 else 0
    rep["findings"]["win_rate_by_abs_score"] = {
        k: {"n": v["n"], "win_rate_pct": pct(v["wins"], v["n"])}
        for k, v in sorted(buckets.items())}

    conf = defaultdict(lambda: {"n": 0, "wins": 0})
    for s in closed:
        c = s.get("confidence") or 0
        b = conf[f"{int(c * 20) * 5}%"]
        b["n"] += 1
        b["wins"] += 1 if (s["pnl_money"] or 0) > 0 else 0
    rep["findings"]["win_rate_by_confidence"] = {
        k: {"n": v["n"], "win_rate_pct": pct(v["wins"], v["n"])}
        for k, v in sorted(conf.items(), key=lambda kv: int(kv[0].rstrip('%')))}

    # ------------------------------------------------------- context tables
    if table_exists(con, "notifications"):
        rep["notifications_recent"] = [dict(r) for r in con.execute(
            "SELECT created_at,kind,title,substr(body,1,300) AS body,instrument "
            "FROM notifications ORDER BY created_at DESC LIMIT 400")]
        rep["notification_errors"] = [dict(r) for r in con.execute(
            "SELECT created_at,title,substr(body,1,300) AS body FROM notifications "
            "WHERE body LIKE '%недоступен%' OR body LIKE '%отклон%' "
            "   OR title LIKE '%отклон%' OR body LIKE '%ошибка%' "
            "ORDER BY created_at DESC LIMIT 200")]
    if table_exists(con, "settings"):
        rep["settings"] = {r["key"]: redact(json.loads(r["value"]))
                           for r in con.execute("SELECT key,value FROM settings")
                           if r["value"]}
    if table_exists(con, "backtest_runs"):
        rep["backtest_runs"] = [
            {"id": r["id"], "created_at": r["created_at"],
             "instrument": r["instrument"], "timeframe": r["timeframe"],
             "params": json.loads(r["params"] or "{}"),
             "metrics": json.loads(r["metrics"] or "{}")}
            for r in con.execute("SELECT * FROM backtest_runs ORDER BY created_at")]

    # full signal rows last (bulky but this is the point of the export)
    rep["signals"] = signals

    with open(args.out, "w") as f:
        json.dump(rep, f, indent=1, default=str)

    _summary(rep, args.out)
    con.close()


def _hist(rs):
    edges = [(-99, -1.5), (-1.5, -0.9), (-0.9, -0.3), (-0.3, 0.3),
             (0.3, 0.9), (0.9, 1.5), (1.5, 99)]
    out = {}
    for lo, hi in edges:
        n = sum(1 for r in rs if lo <= r < hi)
        out[f"[{lo},{hi})"] = n
    return out


def _summary(rep, out):
    c, f = rep["counts"], rep["findings"]
    print(f"\nwrote {out}\n")
    print(f"signals {c['signals_total']}  closed {c['closed']}  open {c['open']}")
    print(f"range   {c['first_created']}  ->  {c['last_created']}")
    print(f"status  {c['by_status']}")
    w = f["win_rate"]
    print(f"\nwins {w['wins']}  losses {w['losses']}  zero-pnl {w['exactly_zero_pnl']}")
    print(f"win rate (all closed)      {w['win_rate_pct_all_closed']}%")
    print(f"win rate (excluding zeros) {w['win_rate_pct_excluding_zeros']}%")
    print(f"break-even needed @RR1.8   {w['breakeven_needed_at_rr_1_8_pct']}%")
    if f.get("zero_pnl_causes"):
        print(f"\nzero-pnl causes  {f['zero_pnl_causes']}")
    if f.get("risk_amount"):
        print(f"risk_amount      {f['risk_amount']}")
    if f.get("realised_R"):
        r = f["realised_R"]
        print(f"\nrealised R  mean {r['mean']}  median {r['median']}  "
              f"min {r['min']}  max {r['max']}")
        print(f"histogram   {r['histogram']}")
    print(f"\napp vs broker    {f['app_vs_broker']}")
    print("\nworst instruments:")
    for k, v in list(rep["by_instrument"].items())[:12]:
        print(f"  {k:<12} n={v['n']:<4} WR={str(v['win_rate_pct']):<6} "
              f"app={v['money_eur']:<10} broker={v['broker_eur']}")
    print("\nNOTE: credentials are redacted; this file is safe to share.")


if __name__ == "__main__":
    main()
