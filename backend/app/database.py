from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}, future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Lightweight SQLite migration: create_all only creates missing tables, so
# columns added to existing tables are declared here and ALTERed in on start.
_COLUMN_ADDS: dict[str, dict[str, str]] = {
    "signals": {
        "strategy": "VARCHAR(64) NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "ai_review": "TEXT NOT NULL DEFAULT ''",
        "current_sl": "FLOAT",
        "be_moved": "INTEGER NOT NULL DEFAULT 0",
        "partial_taken": "INTEGER NOT NULL DEFAULT 0",
        "partial_pnl": "FLOAT NOT NULL DEFAULT 0.0",
        "mt5_pnl": "FLOAT",
        "mt5_volume": "FLOAT NOT NULL DEFAULT 0.0",
        "mt5_orders": "INTEGER NOT NULL DEFAULT 0",
    },
    "news_analyses": {
        "news_items": "JSON NOT NULL DEFAULT '[]'",
    },
}


def _migrate() -> None:
    with engine.begin() as conn:
        for table, columns in _COLUMN_ADDS.items():
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if not rows:
                continue  # table does not exist yet — create_all handles it
            existing = {r[1] for r in rows}
            for col, ddl in columns.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate()
