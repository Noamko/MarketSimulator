import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SCHEMA_VERSION = 2


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    """Migrate from the original singleton-account schema to the multi-user one.

    Strategy: create the `users` table, seed it from the existing `account` row
    (preserving cash_cents and created_at) under the name "default", then add
    `user_id` columns to `trades` and `lots` populated with that user's id, and
    drop `account`.
    """
    legacy_cash = 0
    legacy_created_at = None
    if _table_exists(conn, "account"):
        row = conn.execute(
            "SELECT cash_cents, created_at FROM account WHERE id = 1"
        ).fetchone()
        if row is not None:
            legacy_cash = int(row["cash_cents"])
            legacy_created_at = row["created_at"]

    conn.execute("""
        CREATE TABLE users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            cash_cents INTEGER NOT NULL,
            created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if _table_exists(conn, "account"):
        # Seed the migrated user with the legacy cash + created_at.
        if legacy_created_at is not None:
            conn.execute(
                "INSERT INTO users (id, name, cash_cents, created_at) VALUES (1, 'default', ?, ?)",
                (legacy_cash, legacy_created_at),
            )
        else:
            conn.execute(
                "INSERT INTO users (id, name, cash_cents) VALUES (1, 'default', ?)",
                (legacy_cash,),
            )

    # Add user_id to trades / lots if they pre-exist.
    if _table_exists(conn, "trades"):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
        if "user_id" not in cols:
            conn.execute("ALTER TABLE trades ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.execute("UPDATE trades SET user_id = 1")
    if _table_exists(conn, "lots"):
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(lots)").fetchall()}
        if "user_id" not in cols:
            conn.execute("ALTER TABLE lots ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.execute("UPDATE lots SET user_id = 1")

    if _table_exists(conn, "account"):
        conn.execute("DROP TABLE account")


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add the `webhooks` table. It is brand-new, so the idempotent
    `CREATE TABLE IF NOT EXISTS` in schema.sql (re-applied below) does the actual
    work. This hook exists for symmetry with the v0→v1 migration and as a home
    for any future ALTERs to the webhooks schema."""
    pass


def bootstrap(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        current_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current_version < 1:
            # Only migrate if we have old artifacts; otherwise schema.sql does the work.
            needs_migration = _table_exists(conn, "account") and not _table_exists(conn, "users")
            if needs_migration:
                _migrate_v0_to_v1(conn)
        if current_version < 2:
            _migrate_v1_to_v2(conn)
        # Always re-apply schema (CREATE IF NOT EXISTS) for any missing pieces.
        conn.executescript(SCHEMA_PATH.read_text())
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    finally:
        conn.close()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
