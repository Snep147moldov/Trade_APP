"""Runtime configuration: credentials entered in the app (DB) take priority
over environment variables. Also: Anthropic usage logging with cost estimates.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..config import (
    DEFAULT_APP_CONFIG,
    ENV_ANTHROPIC_API_KEY,
    ENV_EODHD_API_KEY,
    ENV_OANDA_ACCOUNT_ID,
    ENV_OANDA_API_KEY,
    ENV_OANDA_ENV,
    ENV_TELEGRAM_BOT_TOKEN,
    ENV_TWELVEDATA_API_KEY,
    MODEL_PRICES,
)
from ..database import SessionLocal
from ..models import ApiUsage, Setting

_CRED_KEY = "credentials"
_APP_KEY = "app"

_CRED_FIELDS = {
    "twelvedata_api_key": ENV_TWELVEDATA_API_KEY,
    "eodhd_api_key": ENV_EODHD_API_KEY,
    "oanda_api_key": ENV_OANDA_API_KEY,
    "oanda_account_id": ENV_OANDA_ACCOUNT_ID,
    "oanda_env": ENV_OANDA_ENV or "practice",
    "anthropic_api_key": ENV_ANTHROPIC_API_KEY,
    "telegram_bot_token": ENV_TELEGRAM_BOT_TOKEN,
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
}


def get_credentials(db: Session) -> dict[str, str]:
    """Credentials + the selected data provider mode (candles.py needs both)."""
    row = db.get(Setting, _CRED_KEY)
    stored = row.value if row else {}
    creds = {k: (stored.get(k) or env_default) for k, env_default in _CRED_FIELDS.items()}
    creds["data_provider"] = get_app_config(db)["data_provider"]
    return creds


def update_credentials(db: Session, patch: dict[str, Any]) -> None:
    row = db.get(Setting, _CRED_KEY)
    current = dict(row.value) if row else {}
    for k, v in patch.items():
        if k in _CRED_FIELDS and isinstance(v, str):
            current[k] = v.strip()
    if row:
        row.value = current
    else:
        db.add(Setting(key=_CRED_KEY, value=current))
    db.commit()


def mask(value: str) -> str:
    if not value:
        return ""
    return "•" * 6 + value[-4:] if len(value) > 4 else "•" * len(value)


def get_app_config(db: Session) -> dict[str, Any]:
    row = db.get(Setting, _APP_KEY)
    merged = dict(DEFAULT_APP_CONFIG)
    if row:
        merged.update({k: v for k, v in row.value.items() if k in DEFAULT_APP_CONFIG})
    return merged


def update_app_config(db: Session, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_app_config(db)
    for k, v in patch.items():
        if k not in DEFAULT_APP_CONFIG:
            continue
        expected = type(DEFAULT_APP_CONFIG[k])
        if expected is bool and isinstance(v, bool):
            current[k] = v
        elif expected is int and isinstance(v, (int, float)):
            current[k] = int(v)
        elif expected is list and isinstance(v, list):
            current[k] = v
        elif expected is str and isinstance(v, str):
            current[k] = v.strip()
    row = db.get(Setting, _APP_KEY)
    if row:
        row.value = current
    else:
        db.add(Setting(key=_APP_KEY, value=current))
    db.commit()
    return current


def is_simulated(db: Session) -> bool:
    from .candles import active_provider

    return active_provider(get_credentials(db)) == "simulation"


def data_provider_name(db: Session) -> str:
    from .candles import active_provider

    return active_provider(get_credentials(db))


def is_ai_enabled(db: Session) -> bool:
    return bool(get_credentials(db)["anthropic_api_key"])


def log_usage(model: str, purpose: str, input_tokens: int, output_tokens: int) -> None:
    prices = MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    db = SessionLocal()
    try:
        db.add(ApiUsage(
            model=model,
            purpose=purpose,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
        ))
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------
# Custom instruments (user-added tickers) — persisted, loaded at startup
# --------------------------------------------------------------------------

_CUSTOM_KEY = "custom_instruments"


def load_custom_instruments() -> None:
    from ..catalog import register_custom

    db = SessionLocal()
    try:
        row = db.get(Setting, _CUSTOM_KEY)
        for item in (row.value if row else []):
            try:
                register_custom(item["symbol"], item.get("name", ""),
                                item.get("category", "stocks"), item.get("price"))
            except (ValueError, KeyError):
                continue
    finally:
        db.close()


def persist_custom_instrument(db: Session, entry: dict) -> None:
    row = db.get(Setting, _CUSTOM_KEY)
    items = list(row.value) if row else []
    if not any(i.get("symbol") == entry["symbol"] for i in items):
        items.append({
            "symbol": entry["symbol"], "name": entry["name"],
            "category": entry["category"], "price": entry["base_price"],
        })
        if row:
            row.value = items
        else:
            db.add(Setting(key=_CUSTOM_KEY, value=items))
        db.commit()
