import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH, STARTING_CASH_CENTS

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def bootstrap(db_path: Path = DB_PATH, starting_cash_cents: int = STARTING_CASH_CENTS) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        row = conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO account (id, cash_cents) VALUES (1, ?)",
                (starting_cash_cents,),
            )
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
