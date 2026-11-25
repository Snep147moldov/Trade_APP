import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

log = logging.getLogger(__name__)

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
        # existing rows predate the confirmation gate — they were opened under
        # the old "no confirmation" behaviour, so they stay untouched
        "confirm_state": "VARCHAR(12) NOT NULL DEFAULT 'not_required'",
        "confirm_expires_at": "DATETIME",
    },
    "news_analyses": {
        "news_items": "JSON NOT NULL DEFAULT '[]'",
    },
    "users": {
        "email": "VARCHAR(160) NOT NULL DEFAULT ''",
        "language": "VARCHAR(5) NOT NULL DEFAULT 'ru'",
        "reset_hash": "VARCHAR(256)",
        "reset_expires_at": "DATETIME",
    },
    "subscriptions": {
        "provider": "VARCHAR(16) NOT NULL DEFAULT ''",
        "external_id": "VARCHAR(64) NOT NULL DEFAULT ''",
        "customer_ref": "VARCHAR(64) NOT NULL DEFAULT ''",
        "manage_url": "VARCHAR(512) NOT NULL DEFAULT ''",
        "billing_interval": "VARCHAR(8) NOT NULL DEFAULT ''",
        "synced_at": "DATETIME",
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


#: Таблицы со ссылкой на users.id и колонка времени, по которой видно, что
#: строка старше своего владельца (а значит, досталась ему от удалённого).
USER_REF_TABLES: dict[str, str] = {
    "auth_tokens": "created_at",
    "audit_log": "created_at",
    "subscriptions": "created_at",
    "payments": "created_at",
    "billing_notices": "created_at",
    "user_events": "created_at",
    "customer_profiles": "updated_at",
}


def _never_reuse_user_ids(eng=None) -> dict[str, int] | None:
    """Пересобрать `users` с AUTOINCREMENT — один раз, на старой базе.

    Без AUTOINCREMENT SQLite выдаёт новому аккаунту id удалённого, если тот был
    последним, и новый наследует всё, что за удалённым осталось. 25.11.2026 так
    `maib-test@` получил id 3 вместе с двумя пробными подписками, событиями и
    записями журнала двух удалённых аккаунтов — с оплаченной подпиской было бы
    бесплатно подарено чужое.

    Заодно отцепляет уже унаследованное: строка старше своего владельца ему
    принадлежать не может. Доступ, напоминания, события, заметки — удаляются;
    журнал остаётся без владельца (в нём есть имя); оплаты не трогаются — это
    бухгалтерия, их только считаем в лог.

    Всё в одной транзакции SQLite: на сбое таблица остаётся как была.

    :returns: Сколько строк отцеплено по таблицам, или None — пересборка не нужна
    """
    from .models import User

    eng = eng or engine
    raw = eng.raw_connection()
    dbapi = raw.driver_connection
    old_isolation = dbapi.isolation_level
    # сами управляем транзакцией: pysqlite не открывает её перед DDL,
    # и переименование таблицы закоммитилось бы отдельно от остального
    dbapi.isolation_level = None
    cur = dbapi.cursor()
    try:
        row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if row is None or "AUTOINCREMENT" in (row[0] or "").upper():
            return None
        cur.execute("BEGIN IMMEDIATE")
        existing = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        tables = {t: col for t, col in USER_REF_TABLES.items() if t in existing}

        detached: dict[str, int] = {}
        older = "{t}.{col} < (SELECT u.created_at FROM users u WHERE u.id = {t}.user_id)"
        for t, col in tables.items():
            cond = older.format(t=t, col=col)
            if t == "payments":
                n = cur.execute(f"SELECT COUNT(*) FROM payments WHERE {cond}").fetchone()[0]
                if n:
                    log.warning("payments: %d оплат старше своего владельца — не трогаю, "
                                "проверьте вручную", n)
                continue
            if t == "audit_log":
                n = cur.execute(f"UPDATE audit_log SET user_id = NULL WHERE {cond}").rowcount
            else:
                n = cur.execute(f"DELETE FROM {t} WHERE {cond}").rowcount
            if n:
                detached[t] = n

        cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        keep = ", ".join(f'"{c}"' for c in cols if c in User.__table__.c)
        cur.execute("ALTER TABLE users RENAME TO users__old")
        for (name,) in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='users__old' AND sql IS NOT NULL").fetchall():
            cur.execute(f'DROP INDEX "{name}"')
        from sqlalchemy.schema import CreateIndex, CreateTable
        cur.execute(str(CreateTable(User.__table__).compile(dialect=eng.dialect)))
        for index in User.__table__.indexes:
            cur.execute(str(CreateIndex(index).compile(dialect=eng.dialect)))
        cur.execute(f"INSERT INTO users ({keep}) SELECT {keep} FROM users__old")
        cur.execute("DROP TABLE users__old")

        # счётчик — выше любого id, на который ещё что-то ссылается: удалённые
        # аккаунты оставили оплаты и журнал под своими id, и эти id заняты навсегда
        high = cur.execute("SELECT COALESCE(MAX(id), 0) FROM users").fetchone()[0]
        for t in tables:
            high = max(high, cur.execute(
                f"SELECT COALESCE(MAX(user_id), 0) FROM {t}").fetchone()[0] or 0)
        cur.execute("DELETE FROM sqlite_sequence WHERE name = 'users'")
        cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('users', ?)", (high,))
        cur.execute("COMMIT")
        log.warning("users: пересобрана с AUTOINCREMENT, следующий id > %d; отцеплено %s",
                    high, detached or "ничего")
        return detached
    except Exception:
        if dbapi.in_transaction:
            cur.execute("ROLLBACK")
        raise
    finally:
        cur.close()
        dbapi.isolation_level = old_isolation
        raw.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate()
    _never_reuse_user_ids()
