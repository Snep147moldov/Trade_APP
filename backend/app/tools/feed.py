"""Диагностика ленты котировок: кто отдаёт свечи и настоящие ли они.

Появилась после суток, потраченных на однострочники в SSH: подписка Twelve Data
слетела, get_candles молча ушёл на встроенный симулятор, а каждая проверка
требовала питоновского кода в кавычках внутри кавычек внутри docker exec.
Здесь то же самое, но без экранирования.

Заодно умеет прописать ключи — UI иногда не сохраняет, а проверять «сохранилось
ли» отдельной командой дороже, чем сделать это здесь же.

Запуск:
    docker compose exec -T backend python3 -m app.tools.feed
    docker compose exec -T backend python3 -m app.tools.feed --set-td-key КЛЮЧ
    docker compose exec -T backend python3 -m app.tools.feed --provider oanda \\
        --oanda-key ТОКЕН --oanda-account 101-004-1234567-001
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from ..database import SessionLocal
from ..services.candles import (active_provider, get_candles, is_simulated,
                                pip_size)
from ..services.runtime import (get_app_config, get_credentials,
                                update_app_config, update_credentials)

PROBE = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "NZD_CAD", "AUD_CHF"]
TD_HOST = "https://api.twelvedata.com"


def _mask(key: str) -> str:
    return f"{key[:6]}...{key[-4:]} (длина {len(key)})" if key else "ПУСТО"


async def _td_probe(key: str) -> None:
    """Сырые ответы Twelve Data. Провайдер сообщает и «нет такого символа», и
    «подписка кончилась» одинаково — телом с кодом 200, — поэтому смотреть надо
    именно тело, а не статус."""
    if not key:
        print("  ключ не задан — опрос пропущен")
        return
    async with httpx.AsyncClient(timeout=25) as client:
        for path, params in (
            ("/api_usage", {"apikey": key}),
            ("/time_series", {"symbol": "EUR/USD", "interval": "1h",
                              "outputsize": 2, "apikey": key}),
        ):
            try:
                r = await client.get(TD_HOST + path, params=params)
                body = json.dumps(r.json(), ensure_ascii=False)
            except Exception as exc:
                print(f"  {path:14} ОШИБКА {type(exc).__name__}: {exc}")
                continue
            print(f"  {path:14} HTTP {r.status_code}  {body[:260]}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-td-key", default=None, help="ключ Twelve Data")
    ap.add_argument("--set-eodhd-key", default=None)
    ap.add_argument("--oanda-key", default=None)
    ap.add_argument("--oanda-account", default=None)
    ap.add_argument("--oanda-env", default=None, choices=["practice", "live"])
    ap.add_argument("--provider", default=None,
                    choices=["auto", "twelvedata", "eodhd", "oanda", "simulation"])
    ap.add_argument("--tf", default="1h")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        patch: dict[str, Any] = {}
        if args.set_td_key:
            patch["twelvedata_api_key"] = args.set_td_key
        if args.set_eodhd_key:
            patch["eodhd_api_key"] = args.set_eodhd_key
        if args.oanda_key:
            patch["oanda_api_key"] = args.oanda_key
        if args.oanda_account:
            patch["oanda_account_id"] = args.oanda_account
        if args.oanda_env:
            patch["oanda_env"] = args.oanda_env
        if patch:
            update_credentials(db, patch)
            print(f"записано в credentials: {', '.join(sorted(patch))}")
        if args.provider:
            update_app_config(db, {"data_provider": args.provider})
            print(f"провайдер переключён на {args.provider}")
        if patch or args.provider:
            print("ВАЖНО: перезапустить backend, иначе в живом процессе "
                  "останется прежний чёрный список символов\n")

        creds = get_credentials(db)
        cfg = get_app_config(db)

        print("=" * 70)
        print("ЛЕНТА КОТИРОВОК")
        print("=" * 70)
        print(f"  режим (data_provider) : {cfg.get('data_provider')}")
        print(f"  активный провайдер    : {active_provider(creds)}")
        print(f"  Twelve Data ключ      : {_mask(creds.get('twelvedata_api_key') or '')}")
        print(f"  EODHD ключ            : {_mask(creds.get('eodhd_api_key') or '')}")
        print(f"  OANDA ключ            : {_mask(creds.get('oanda_api_key') or '')}"
              f"  счёт {creds.get('oanda_account_id') or '—'}"
              f"  ({creds.get('oanda_env') or '—'})")

        print("\n--- ОТВЕТ TWELVE DATA ---")
        await _td_probe(creds.get("twelvedata_api_key") or "")

        print(f"\n--- СВЕЧИ {args.tf} ---")
        now = datetime.now(timezone.utc).timestamp()
        bad = 0
        for sym in PROBE:
            try:
                candles = await get_candles(creds, sym, args.tf, 60)
            except Exception as exc:
                bad += 1
                print(f"  {sym:9} ОШИБКА {type(exc).__name__}")
                continue
            last = candles[-1]
            if is_simulated(candles):
                bad += 1
                print(f"  {sym:9} СИНТЕТИКА  {last['close']}"
                      f"   <- сигналы по нему заблокированы")
            else:
                age = (now - last["time"]) / 60
                print(f"  {sym:9} рынок      {last['close']}"
                      f"   последний бар {age:.0f} мин назад"
                      f"   пункт {pip_size(sym)}")

        print()
        if bad:
            print(f"  {bad} из {len(PROBE)} без настоящих данных — движок по ним "
                  "сигналы не строит (это защита, а не поломка).")
            print("  Цены вида 1.0850 / 0.89 / 196.85 — это base_price из "
                  "каталога, то есть встроенный симулятор.")
        else:
            print("  все пары на реальных данных — движок работает штатно.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
