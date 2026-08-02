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
    region = await _fresh_region(db, creds)
    r = await _api("GET",
                   f"{_client_host(region)}/users/current/accounts/{acc}/symbols",
                   token, timeout=30)
    if not r["ok"] or not isinstance(r["data"], list):
        # держим прошлый список: лучше слегка устаревший, чем пустой (пустой
        # снимает всякую проверку и сигнал снова дойдёт до отклонения брокером)
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


async def tradable(db, instrument: str) -> bool:
    """Дешёвая проверка «брокер вообще даёт торговать этим инструментом».

    Нужна ДО показа сигнала пользователю: список символов кэшируется на час,
    поэтому вызов почти всегда без сети. Любая ошибка -> True (не мешаем
    работе, решение останется за ордером).
    """
    try:
        creds = get_credentials(db)
        if not is_configured(creds):
            return True  # брокер не подключён — фильтровать нечего
        ok, _ = await symbol_supported(db, instrument)
        return ok
    except Exception:
        return True


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


BROKER_MIN_LOT = 0.01
# насколько реальный объём может превысить задуманный риск, прежде чем сделку
# лучше не открывать вовсе. 1.25 = допускаем 25% сверху из-за округления лота.
MAX_RISK_OVERSHOOT = 1.25


def units_to_lots(instrument: str, units: float, max_lots: float = 0.5,
                  max_overshoot: float | None = None) -> float:
    """App position size (units of base asset) -> broker lots.

    Returns 0.0 when the risk CANNOT be respected — i.e. the smallest lot the
    broker accepts already risks more than the app intends. The old version
    clamped up to 0.01 instead, which silently multiplied the real risk: on
    XAU (100 oz/lot) a 9.91 EUR signal became a 27 EUR position at 0.01 lot
    and 54 EUR at 0.02 — measured against live deals, losses came in at 1.9x
    the intended risk while wins came in at 0.05x.
    """
    if units <= 0:
        return 0.0
    tol = MAX_RISK_OVERSHOOT if max_overshoot is None else float(max_overshoot)
    cs = contract_size(instrument)
    lots = units / cs
    lots = min(round(lots, 2), max(BROKER_MIN_LOT, max_lots))
    if lots < BROKER_MIN_LOT:
        lots = BROKER_MIN_LOT
    # проверяем ИТОГОВЫЙ объём, а не только случай округления в ноль: на
    # USD/JPY 700 единиц округлялись до 0.01 лота (1000 единиц) — риск ×1.43
    # проходил мимо проверки, потому что 0.01 уже не меньше минимального лота
    if (lots * cs) / units > tol:
        return 0.0
    return lots


def risk_overshoot(instrument: str, units: float, lots: float) -> float:
    """Во сколько раз реальная позиция крупнее задуманной (1.0 = точно)."""
    if units and units > 0 and lots > 0:
        return (lots * contract_size(instrument)) / units
    return 1.0


def signal_lots(cfg: dict, instrument: str, units: float | None,
                max_overshoot: float | None = None, orders: int = 1) -> float:
    """Lot for ONE order out of `orders` covering the same signal.

    The signal's risk is DIVIDED across the ladder: N orders at the full size
    would risk N times what the app promised. That is exactly what happened
    with autotrade_orders_per_signal=3 — a signal advertising 1.37 EUR opened
    three positions and lost 4.11 EUR, and every «Купить ×3» tap tripled the
    stake the user thought they were taking.

    0.0 means «нельзя соблюсти риск» — ордер не отправляется.

    `max_overshoot` приходит из НАСТРОЕК СТРАТЕГИИ (max_risk_overshoot), а не
    из app-config: раньше здесь читался cfg, где такого ключа нет, и значение
    из UI молча игнорировалось в пользу дефолта."""
    if cfg.get("autotrade_risk_sizing"):
        # без размера от риск-менеджера торговать нельзя: раньше units=0
        # (округление позиции меньше единицы на металлах) проваливалось на
        # фиксированный autotrade_lots, и заявленный риск игнорировался целиком
        if not units or float(units) <= 0:
            return 0.0
        per_order = float(units) / max(1, int(orders))
        return units_to_lots(instrument, per_order,
                             float(cfg.get("autotrade_max_lots", 0.5)),
                             max_overshoot)
    return float(cfg.get("autotrade_lots", 0.01))


def executability(cfg: dict, settings: dict, instrument: str,
                  units: float | None, risk_amount: float | None,
                  orders: int = 1) -> dict[str, Any]:
    """Можно ли вообще исполнить сигнал минимальным лотом брокера.

    Считается на ОДИН ордер из `orders`: риск сигнала делится на всю лестницу,
    поэтому чем больше ордеров, тем меньше каждый — и тем чаще он не влезает
    в минимальный лот брокера. `lots` — объём одного ордера, `risk_eur` —
    суммарный риск ПО ВСЕМ ордерам (именно его видит пользователь).

    Возвращает {ok, overshoot, lots, risk_eur, needs_confirm, reason}:
      ok=True,  needs_confirm=False — риск соблюдён, обычная кнопка «Купить»;
      ok=True,  needs_confirm=True  — влезает только с превышением риска (до
                                      max_manual_overshoot): кнопка есть, но
                                      нажатие требует ВТОРОГО подтверждения;
      ok=False                      — даже ручное превышение выше потолка:
                                      кнопки нет, сделка не предлагается.
    """
    n = max(1, int(orders))
    if not cfg.get("autotrade_risk_sizing"):
        # фиксированный объём: риск-менеджер не участвует, оценивать нечего
        return {"ok": True, "overshoot": 1.0, "needs_confirm": False,
                "lots": signal_lots(cfg, instrument, units, orders=n),
                "risk_eur": risk_amount, "reason": ""}
    if not units or float(units) <= 0:
        # размер не рассчитан — торговать вслепую нельзя
        return {"ok": False, "overshoot": 0.0, "needs_confirm": False,
                "lots": 0.0, "risk_eur": risk_amount,
                "reason": "риск-менеджер не рассчитал размер позиции"}

    tol = float(settings.get("max_risk_overshoot", MAX_RISK_OVERSHOOT))
    ceiling = float(settings.get("max_manual_overshoot", 3.0))
    max_lots = float(cfg.get("autotrade_max_lots", 0.5))
    per_order = float(units) / n

    lots = units_to_lots(instrument, per_order, max_lots, tol)
    if lots > 0:
        # превышение считаем по всей лестнице: n ордеров по lots против
        # задуманного объёма сигнала
        overshoot = risk_overshoot(instrument, float(units), lots * n)
        return {"ok": True, "overshoot": overshoot, "needs_confirm": False,
                "lots": lots, "risk_eur": (risk_amount or 0.0) * overshoot,
                "reason": ""}

    # риск не влезает: считаем превышение по объёму, который реально уйдёт
    # брокеру при поднятом потолке (обычно это минимальный лот на каждый ордер)
    forced = units_to_lots(instrument, per_order, max_lots, ceiling)
    effective = (forced if forced > 0 else BROKER_MIN_LOT) * n
    overshoot = risk_overshoot(instrument, float(units), effective)
    real_risk = (risk_amount or 0.0) * overshoot
    if forced > 0:
        return {"ok": True, "overshoot": overshoot, "needs_confirm": True,
                "lots": forced, "risk_eur": real_risk,
                "reason": (f"минимальный лот брокера ({BROKER_MIN_LOT}) ×{n} "
                           f"рискует ×{overshoot:.1f} от заданного")}
    return {"ok": False, "overshoot": overshoot, "needs_confirm": False,
            "lots": 0.0, "risk_eur": real_risk,
            "reason": (f"минимальный лот ×{n} рискует ×{overshoot:.1f} "
                       f"(потолок ×{ceiling:.1f}) — нужен депозит крупнее, "
                       f"меньше ордеров или более узкий стоп")}


def scale_out_take_profits(direction: str, entry: float, stop_loss: float,
                           take_profit: float, n: int, precision: int) -> list[float]:
    """Split one signal into n orders with staggered take-profits (scale-out).

    The ladder is centred on the signal's own target so the AVERAGE take-profit
    always equals it: for every order that banks early, one runs equally far
    past the target. All orders share the signal's stop-loss.

    The previous ladder started at +1R and only extended upward, which quietly
    lowered the realised reward below the advertised risk:reward — worst at
    n=2 (mean +1.4R against a full -1R loss, i.e. break-even win rate 41.7%
    instead of the advertised 35.7%). Losses were always the full stop, so the
    ladder made winners smaller without making losers smaller.
    """
    n = max(1, min(int(n), 5))
    if n == 1:
        return [take_profit]
    side = 1.0 if direction == "BUY" else -1.0
    tp_dist = abs(take_profit - entry)
    if tp_dist <= 0:
        return [round(take_profit, precision)] * n
    # symmetric spread around the target: the mean of the multipliers is 1.0
    spread = 0.5           # innermost order takes 50% of the target distance
    if n == 2:
        mults = [1.0 - spread, 1.0 + spread]
    else:
        step = 2.0 * spread / (n - 1)
        mults = [1.0 - spread + step * i for i in range(n)]
    return [round(entry + side * tp_dist * m, precision) for m in mults]


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
        # тайм-аут не означает «ордера нет»: запрос мог дойти до брокера, а
        # ответ потеряться. Помечаем отдельно, чтобы вызывающий мог проверить
        # позиции, а не рапортовать отказ и провоцировать повторное нажатие.
        timed_out = isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout,
                                     httpx.PoolTimeout, httpx.ConnectTimeout))
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "timeout": timed_out}


async def _fresh_region(db, creds: dict) -> str:
    """Re-fetch the account's actual MetaApi region instead of trusting the
    cached settings value: MetaApi can redeploy an account to a different
    region than the one saved at provisioning time, and a stale region gives
    NotFoundError ("too many unexisting or undeployed trading accounts") on
    every client-api call (symbols/trade/positions) even though status() —
    which does refetch — reports the account fine."""
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    r = await _api("GET", f"{PROVISIONING_HOST}/users/current/accounts/{acc_id}", token)
    region = (r["data"].get("region") if r["ok"] else None) or creds["mt5_region"] or "new-york"
    if region != creds["mt5_region"]:
        update_credentials(db, {"mt5_region": region})
    return region


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
    region = await _fresh_region(db, creds)
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
    # 0 лотов = риск-менеджер не смог уложиться в заданный риск минимальным
    # лотом брокера. Раньше объём молча поднимался до 0.01 и позиция рисковала
    # кратно больше задуманного — именно так счёт и терял деньги.
    if not lots or float(lots) <= 0:
        return {"ok": False,
                "error": f"объём 0: минимальный лот брокера по {instrument} "
                         f"рискует больше заданного риска — сделка пропущена"}
    lots = round(float(lots), 2)
    if lots < 0.01:
        return {"ok": False,
                "error": f"объём {lots} ниже минимального лота брокера (0.01)"}
    token, acc_id = creds["metaapi_token"], creds["mt5_account_id"]
    region = await _fresh_region(db, creds)
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
        # тайм-аут: ответ потерян, но ордер мог исполниться. Спрашиваем брокера
        # напрямую — иначе пользователь видит «отклонён», жмёт ещё раз и
        # открывает вторую позицию поверх уже существующей.
        if r.get("timeout") and comment:
            await asyncio.sleep(2)  # даём брокеру дописать позицию
            check = await positions(db)
            if check.get("ok"):
                tag = comment[:26]
                for p in check["positions"]:
                    if (p.get("comment") or "") == tag and p.get("symbol") == symbol:
                        return {"ok": True, "symbol": symbol, "lots": lots,
                                "order_id": None, "position_id": p.get("id"),
                                "recovered": True}
            return {"ok": False,
                    "error": ("тайм-аут MetaApi; позиция у брокера НЕ найдена — "
                              "ордер, вероятно, не прошёл")}
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
    region = await _fresh_region(db, creds)
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
    region = await _fresh_region(db, creds)
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
    region = await _fresh_region(db, creds)
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
    region = await _fresh_region(db, creds)
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
