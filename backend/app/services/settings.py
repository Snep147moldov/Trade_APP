from typing import Any

from sqlalchemy.orm import Session

from .. import catalog
from ..config import DEFAULT_SETTINGS
from ..models import Setting

_KEY = "strategy"
_CATEGORY_KEY = "category_risk"

_INT_KEYS = {"max_daily_losses"}
_LIST_KEYS = {"blocked_instruments"}
_INT_LIST_KEYS = {"blocked_hours_utc"}
_STR_KEYS = {
    "sizing_mode": ("fixed", "half_kelly"),
    "signal_mode": ("conservative", "aggressive"),
    "factor_signs": ("original", "measured", "inverted"),
}

# per-category strategy overrides: только эти два поля, остальное — из
# глобальных настроек. None/отсутствие в оверрайде = наследует глобальное.
_CATEGORY_FIELDS = ("risk_per_trade_pct", "risk_reward")
_CATEGORIES = {c for c, _ in catalog.CATEGORIES}


def get_settings(db: Session) -> dict[str, Any]:
    row = db.get(Setting, _KEY)
    merged = dict(DEFAULT_SETTINGS)
    if row:
        merged.update({k: v for k, v in row.value.items() if k in DEFAULT_SETTINGS})
    return merged


def update_settings(db: Session, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_settings(db)
    for k, v in patch.items():
        if k not in DEFAULT_SETTINGS:
            continue
        default = DEFAULT_SETTINGS[k]
        if k in _INT_LIST_KEYS:
            if isinstance(v, (list, tuple)):
                current[k] = sorted({int(x) for x in v if 0 <= int(x) <= 23})
        elif k in _LIST_KEYS:
            if isinstance(v, (list, tuple)):
                current[k] = [str(x).strip().upper() for x in v if str(x).strip()]
        elif k in _STR_KEYS:
            if v in _STR_KEYS[k]:
                current[k] = v
        elif isinstance(default, bool):
            if isinstance(v, bool):
                current[k] = v
        elif k in _INT_KEYS:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                current[k] = int(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            current[k] = float(v)
    row = db.get(Setting, _KEY)
    if row:
        row.value = current
    else:
        db.add(Setting(key=_KEY, value=current))
    db.commit()
    return current


def get_category_overrides(db: Session) -> dict[str, dict[str, float]]:
    """{category: {risk_per_trade_pct?, risk_reward?}} — только заданные
    пользователем категории, отсутствующие поля наследуют глобальные."""
    row = db.get(Setting, _CATEGORY_KEY)
    if not row:
        return {}
    return {
        cat: {k: v for k, v in fields.items() if k in _CATEGORY_FIELDS}
        for cat, fields in row.value.items() if cat in _CATEGORIES
    }


def update_category_override(db: Session, category: str,
                             patch: dict[str, Any]) -> dict[str, float]:
    """patch[field] = число -> задаёт оверрайд; patch[field] = None -> сброс
    к глобальному значению для этой категории."""
    if category not in _CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    row = db.get(Setting, _CATEGORY_KEY)
    all_overrides = dict(row.value) if row else {}
    current = dict(all_overrides.get(category, {}))
    for k, v in patch.items():
        if k not in _CATEGORY_FIELDS:
            continue
        if v is None:
            current.pop(k, None)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            current[k] = float(v)
    if current:
        all_overrides[category] = current
    else:
        all_overrides.pop(category, None)
    if row:
        row.value = all_overrides
    else:
        db.add(Setting(key=_CATEGORY_KEY, value=all_overrides))
    db.commit()
    return current


def settings_for_instrument(db: Session, instrument: str) -> dict[str, Any]:
    """get_settings() + оверрайд risk_per_trade_pct/risk_reward для категории
    инструмента, если она настроена. Инструменты без оверрайда не меняются."""
    base = get_settings(db)
    cat = (catalog.meta(instrument) or {}).get("category")
    if not cat:
        return base
    override = get_category_overrides(db).get(cat)
    if not override:
        return base
    return {**base, **override}
