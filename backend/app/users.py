"""Helpers for the User concept.

There is no password / authentication. The frontend keeps the selected user_id
in localStorage and sends it as the `X-User-Id` header on requests that touch
user-owned data. `get_current_user_id` is the FastAPI dependency that reads and
validates it.
"""

import sqlite3

from fastapi import HTTPException, Request

from .db import get_conn


MIN_NAME_LEN = 1
MAX_NAME_LEN = 40
# 100 billion dollars in cents. Just a sanity cap to avoid integer-overflow silliness.
MAX_STARTING_CASH_CENTS = 10_000_000_000_000


def get_current_user_id(request: Request) -> int:
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="missing X-User-Id header")
    try:
        user_id = int(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid X-User-Id header")
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail=f"user {user_id} not found")
    return user_id


def list_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, cash_cents, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def create_user(name: str, starting_cash_cents: int) -> dict:
    name = (name or "").strip()
    if not (MIN_NAME_LEN <= len(name) <= MAX_NAME_LEN):
        raise ValueError(f"name length must be {MIN_NAME_LEN}-{MAX_NAME_LEN} chars")
    if starting_cash_cents < 0 or starting_cash_cents > MAX_STARTING_CASH_CENTS:
        raise ValueError("starting_cash_cents out of allowed range")

    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (name, cash_cents) VALUES (?, ?)",
                (name, starting_cash_cents),
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"a user named {name!r} already exists") from e
            raise
        uid = cur.lastrowid
        row = conn.execute(
            "SELECT id, name, cash_cents, created_at FROM users WHERE id = ?", (uid,)
        ).fetchone()
        return dict(row)
