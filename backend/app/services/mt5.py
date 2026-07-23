"""MetaTrader 5 trading via MetaApi (metaapi.cloud).

The official MetaTrader5 Python package is Windows-only, so the backend talks
to the user's MT5 account through the MetaApi cloud bridge instead: the user
enters a MetaApi token plus the MT5 login/password/server in the app UI, we
provision (or reuse) a cloud account there and place orders over REST.

All functions return {"ok": bool, ...} and never raise — trading must not
kill the scheduler loop.
"""

import asyncio
import time
from typing import Any

import httpx

from ..catalog import meta
from .runtime import get_credentials, update_credentials

PROVISIONING_HOST = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"

# MT5 retcodes considered success for a market order.
_OK_CODES = {0, 10008, 10009}  # ERR_NO_ERROR, PLACED, DONE


def _client_host(region: str) -> str:
    return f"https://mt-client-api-v1.{region}.agiliumtrade.ai"


def mt5_symbol(instrument: str, suffix: str = "") -> str:
    """App instrument -> broker symbol: EUR_USD -> EURUSD, XAU_USD -> XAUUSD,
    NVDA_USD (stock/crypto) -> NVDA. Broker-specific suffixes (EURUSD.m) come
    from the optional mt5_symbol_suffix credential."""
    m = meta(instrument)
    if m and m.get("category") in ("stocks", "crypto"):
        return instrument.removesuffix("_USD") + suffix
    return instrument.replace("_", "") + suffix


def is_configured(creds: dict) -> bool:
    return bool(creds.get("metaapi_token") and creds.get("mt5_account_id"))


# broker symbol universe, cached per account (FusionMarkets ≠ full catalog:
# some crypto/indices/stocks are simply not offered -> UNKNOWN_SYMBOL)
_symbols_cache: dict[str, dict[str, Any]] = {}


async def list_symbols(db) -> set[str]:
    creds = get_credentials(db)
    if not is_configured(creds):
        return set()
    acc = creds["mt5_account_id"]
    ent = _symbols_cache.get(acc)
    if ent and time.time() - ent["ts"] < 3600:
        return ent["symbols"]
    token = creds["metaapi_token"]
    region = creds["mt5_region"] or "new-york"
    r = await _api("GET",
                   f"{_client_host(region)}/users/current/accounts/{acc}/symbols",
                   token, timeout=30)
    if not r["ok"] or not isinstance(r["data"], list):
        return ent["symbols"] if ent else set()
    syms = {str(s) for s in r["data"]}
    _symbols_cache[acc] = {"ts": time.time(), "symbols": syms}
    return syms


async def symbol_supported(db, instrument: str) -> tuple[bool, str]:
    """(поддерживается ли, брокерский символ). Если список символов получить
    не удалось — не блокируем (возвращаем True), пусть решает сам ордер."""
    creds = get_credentials(db)
    broker = mt5_symbol(instrument, creds["mt5_symbol_suffix"])
    syms = await list_symbols(db)
    if not syms:
        return True, broker
    return broker in syms, broker


# Typical CFD contract sizes (units of the base asset per 1.00 lot). Broker
# specifics vary — the computed lot is clamped by autotrade_max_lots.
_CONTRACT_OVERRIDES = {
    "XAU_USD": 100.0,     # 100 oz
    "XAG_USD": 5_000.0,   # 5000 oz
    "XPT_USD": 100.0,
    "XPD_USD": 100.0,
}


def contract_size(instrument: str) -> float:
    if instrument in _CONTRACT_OVERRIDES:
        return _CONTRACT_OVERRIDES[instrument]
    m = meta(instrument) or {}
    if m.get("category") == "forex":
        return 100_000.0  # standard lot
    # indices / crypto / stocks / energy CFDs: usually 1 unit per lot
    return 1.0


def units_to_lots(instrument: str, units: float, max_lots: float = 0.5) -> float:
    """App position size (units of base asset) -> broker lots, clamped to
    [0.01, max_lots] so a mis-sized contract can never nuke the account."""
    if units <= 0:
        return 0.01
    lots = units / contract_size(instrument)
    return max(0.01, min(round(lots, 2), max(0.01, max_lots)))


def signal_lots(cfg: dict, instrument: str, units: float | None) -> float:
    """Lot for one order: risk-based (same sizing the app tracks, split over
    nothing — per order) when autotrade_risk_sizing is on, else the fixed
    autotrade_lots."""
    if cfg.get("autotrade_risk_sizing") and units:
        return units_to_lots(instrument, float(units),
                             float(cfg.get("autotrade_max_lots", 0.5)))
    return float(cfg.get("autotrade_lots", 0.01))


def scale_out_take_profits(direction: str, entry: float, stop_loss: float,
                           take_profit: float, n: int, precision: int) -> list[float]:
    """Split one signal into n orders with staggered take-profits (scale-out):
    the first order banks +1R quickly, the middle keeps the signal's own TP,
    the last runs 50% further. All orders share the same stop-loss."""
    n = max(1, min(int(n), 5))
    if n == 1:
        return [take_profit]
    side = 1.0 if direction == "BUY" else -1.0
    risk = abs(entry - stop_loss)
    tp_dist = abs(take_profit - entry)
    tps = [entry + side * risk, take_profit]           # +1R, full TP
    for i in range(2, n):
        tps.append(entry + side * tp_dist * (1.0 + 0.5 * (i - 1)))
    return [round(tp, precision) for tp in tps[:n]]


async def _api(method: str, url: str, token: str,
               json: dict | None = None, timeout: float = 30) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(method, url, json=json,
                                     headers={"auth-token": token})
        if r.status_code == 204 or not r.content:
            return {"ok": True, "data": {}}
        data = r.json()
        if r.status_code >= 400:
            msg = data.get("message") if isinstance(data, dict) else None
            return {"ok": False, "error": str(msg or f"HTTP {r.status_code}")}
        return {"ok": True, "data": data}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _find_account(token: str, login: str, server: str) -> dict | None:
    r = await _api("GET", f"{PROVISIONING_HOST}/users/current/accounts", token)
    if not r["ok"] or not isinstance(r["data"], list):
        return None
    for acc in r["data"]:
        if str(acc.get("login")) == str(login) and acc.get("server") == server:
            return acc
    return None


async def connect(db) -> dict[str, Any]:
    """Provision (or reuse) the MetaApi cloud account for the entered MT5
    credentials, deploy it and persist its id/region for later calls."""
    creds = get_credentials(db)
    token = creds["metaapi_token"]
    login, password, server = creds["mt5_login"], creds["mt5_password"], creds["mt5_server"]
    if not token:
        return {"ok": False, "error": "нет токена MetaApi (metaapi.cloud)"}
    if not (login and password and server):
        return {"ok": False, "error": "заполните логин, пароль и сервер MT5"}

    acc = await _find_account(token, login, server)
    if acc is None:
        r = await _api("POST", f"{PROVISIONING_HOST}/users/current/accounts", token, {
            "login": str(login),
            "password": password,
            "server": server,
            "platform": "mt5",
            "name": f"Codnixy {login}",
            "magic": 776001,
            "type": "cloud-g2",
        }, timeout=60)
        if not r["ok"]:
            return {"ok": False, "error": f"создание счёта: {r['error']}"}
        acc_id = r["data"].get("id") or r["data"].get("_id")
        acc = {"_id": acc_id}
    acc_id = acc.get("_id") or acc.get("id")
    if not acc_id:
        return {"ok": False, "error": "MetaApi не вернул id счёта"}

    # fetch fresh state; deploy if needed
    r = await _api("GET", f"{PROVISIONING_HOST}/users/current/accounts/{acc_id}", token)
    if not r["ok"]:
        return {"ok": False, "error": r["error"]}
    acc = r["data"]
    if acc.get("state") not in ("DEPLOYED", "DEPLOYING"):
        await _api("POST",
                   f"{PROVISIONING_HOST}/users/current/accounts/{acc_id}/deploy", token)

    update_credentials(db, {
        "mt5_account_id": str(acc_id),
        "mt5_region": acc.get("region") or "new-york",
    })

    # give the terminal a moment, then report the current state
    for _ in range(6):
        st = await status(db)
        if st.get("connected"):
            return st
        await asyncio.sleep(5)
    st = await status(db)
    st.setdefault("hint", "счёт разворачивается — статус обновится через минуту")
    return st


async def status(db) -> dict[str, Any]:
    creds = get_credentials(db)
    if not creds["metaapi_token"]:
        return {"ok": True, "configured": False, "connected": False}
    if not creds["mt5_account_id"]:
        return {"ok": True, "configured": bool(creds["mt5_login"]), "connected": False,
                "state": "NOT_PROVISIONED"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    r = await _api("GET", f"{PROVISIONING_HOST}/users/current/accounts/{acc_id}", token)
    if not r["ok"]:
        return {"ok": False, "configured": True, "connected": False, "error": r["error"]}
    acc = r["data"]
    region = acc.get("region") or creds["mt5_region"] or "new-york"
    out: dict[str, Any] = {
        "ok": True, "configured": True,
        "state": acc.get("state"),
        "connection_status": acc.get("connectionStatus"),
        "connected": acc.get("state") == "DEPLOYED"
        and acc.get("connectionStatus") == "CONNECTED",
        "login": acc.get("login"), "server": acc.get("server"),
    }
    if out["connected"]:
        info = await _api(
            "GET",
            f"{_client_host(region)}/users/current/accounts/{acc_id}/accountInformation",
            token)
        if info["ok"]:
            d = info["data"]
            out["account"] = {
                "broker": d.get("broker"), "currency": d.get("currency"),
                "balance": d.get("balance"), "equity": d.get("equity"),
                "margin": d.get("margin"), "free_margin": d.get("freeMargin"),
                "leverage": d.get("leverage"),
            }
    return out


async def positions(db) -> dict[str, Any]:
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    r = await _api("GET",
                   f"{_client_host(region)}/users/current/accounts/{acc_id}/positions",
                   token)
    if not r["ok"]:
        return r
    rows = [{
        "id": p.get("id"), "symbol": p.get("symbol"),
        "type": "BUY" if p.get("type") == "POSITION_TYPE_BUY" else "SELL",
        "volume": p.get("volume"), "open_price": p.get("openPrice"),
        "current_price": p.get("currentPrice"),
        "stop_loss": p.get("stopLoss"), "take_profit": p.get("takeProfit"),
        "profit": p.get("profit"), "time": p.get("time"),
        "comment": p.get("comment") or "",
    } for p in (r["data"] if isinstance(r["data"], list) else [])]
    return {"ok": True, "positions": rows}


async def place_order(db, instrument: str, direction: str, lots: float,
                      stop_loss: float | None = None,
                      take_profit: float | None = None,
                      comment: str = "") -> dict[str, Any]:
    """Market order with SL/TP attached — the broker then manages the exit
    on its side even if the app is offline."""
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    if direction not in ("BUY", "SELL"):
        return {"ok": False, "error": f"направление {direction} не торгуется"}
    lots = max(0.01, round(float(lots), 2))
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    supported, symbol = await symbol_supported(db, instrument)
    if not supported:
        return {"ok": False,
                "error": f"символ {symbol} недоступен у брокера "
                         f"{creds.get('mt5_server', '')} — торговля этим "
                         f"инструментом невозможна"}
    body: dict[str, Any] = {
        "actionType": "ORDER_TYPE_BUY" if direction == "BUY" else "ORDER_TYPE_SELL",
        "symbol": symbol,
        "volume": lots,
    }
    if stop_loss:
        body["stopLoss"] = stop_loss
    if take_profit:
        body["takeProfit"] = take_profit
    if comment:
        body["comment"] = comment[:26]
    r = await _api("POST",
                   f"{_client_host(region)}/users/current/accounts/{acc_id}/trade",
                   token, body, timeout=45)
    if not r["ok"]:
        return r
    d = r["data"]
    code = d.get("numericCode")
    if code is not None and code not in _OK_CODES:
        return {"ok": False,
                "error": f"{d.get('stringCode') or code}: {d.get('message') or symbol}"}
    return {"ok": True, "symbol": symbol, "lots": lots,
            "order_id": d.get("orderId"), "position_id": d.get("positionId")}


async def modify_position(db, position_id: str, stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict[str, Any]:
    """POSITION_MODIFY: MetaApi removes omitted levels, so callers should pass
    BOTH current values when they only mean to change one of them."""
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    body: dict[str, Any] = {"actionType": "POSITION_MODIFY",
                            "positionId": str(position_id)}
    if stop_loss is not None:
        body["stopLoss"] = stop_loss
    if take_profit is not None:
        body["takeProfit"] = take_profit
    r = await _api("POST",
                   f"{_client_host(region)}/users/current/accounts/{acc_id}/trade",
                   token, body, timeout=45)
    if not r["ok"]:
        return r
    code = r["data"].get("numericCode")
    if code is not None and code not in _OK_CODES:
        return {"ok": False, "error": str(r["data"].get("stringCode") or code)}
    return {"ok": True}


async def place_signal_orders(db, instrument: str, direction: str, lots: float,
                              entry: float, stop_loss: float, take_profit: float,
                              n: int, precision: int,
                              comment_base: str) -> dict[str, Any]:
    """N market orders for one signal with scale-out take-profits and a shared
    stop-loss. Stops at the first broker rejection; reports what got through."""
    tps = scale_out_take_profits(direction, entry, stop_loss, take_profit, n, precision)
    opened: list[dict[str, Any]] = []
    error: str | None = None
    for i, tp in enumerate(tps, start=1):
        tag = f" {i}/{len(tps)}" if len(tps) > 1 else ""
        r = await place_order(db, instrument, direction, lots, stop_loss, tp,
                              comment_base + tag)
        if not r["ok"]:
            error = r.get("error", "ордер отклонён")
            break
        opened.append(r)
    return {
        "ok": bool(opened),
        "opened": len(opened),
        "requested": len(tps),
        "take_profits": tps[:len(opened)],
        "symbol": opened[0]["symbol"] if opened else None,
        "lots": lots,
        "position_ids": [r.get("position_id") for r in opened],
        "error": error,
    }


async def history_deals(db, start_iso: str, end_iso: str) -> dict[str, Any]:
    """Broker deal history [start, end] — the source of truth for real P&L.
    Each deal: type, entryType (IN/OUT), profit, commission, swap, volume,
    positionId, comment, time."""
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    r = await _api(
        "GET",
        f"{_client_host(region)}/users/current/accounts/{acc_id}"
        f"/history-deals/time/{start_iso}/{end_iso}",
        token, timeout=45)
    if not r["ok"]:
        return r
    return {"ok": True, "deals": r["data"] if isinstance(r["data"], list) else []}


async def account_information(db) -> dict[str, Any]:
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    r = await _api(
        "GET",
        f"{_client_host(region)}/users/current/accounts/{acc_id}/accountInformation",
        token)
    if not r["ok"]:
        return r
    return {"ok": True, "account": r["data"]}


async def close_position(db, position_id: str) -> dict[str, Any]:
    creds = get_credentials(db)
    if not is_configured(creds):
        return {"ok": False, "error": "MT5 не подключён"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = creds["mt5_region"] or "new-york"
    r = await _api("POST",
                   f"{_client_host(region)}/users/current/accounts/{acc_id}/trade",
                   token, {"actionType": "POSITION_CLOSE_ID", "positionId": str(position_id)},
                   timeout=45)
    if not r["ok"]:
        return r
    code = r["data"].get("numericCode")
    if code is not None and code not in _OK_CODES:
        return {"ok": False, "error": str(r["data"].get("stringCode") or code)}
    return {"ok": True}
