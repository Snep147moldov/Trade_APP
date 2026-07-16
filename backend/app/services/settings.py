from typing import Any

from sqlalchemy.orm import Session

from ..config import DEFAULT_SETTINGS
from ..models import Setting

_KEY = "strategy"

_INT_KEYS = {"max_daily_losses"}
_STR_KEYS = {
    "sizing_mode": ("fixed", "half_kelly"),
    "signal_mode": ("conservative", "aggressive"),
}


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
        if k in _STR_KEYS:
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
