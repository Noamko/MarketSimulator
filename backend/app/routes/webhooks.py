from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..models import WebhookCreate, WebhookRow, WebhookUpdate
from ..users import get_current_user_id
from .. import webhooks

router = APIRouter()


def _row_to_model(row) -> WebhookRow:
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    d["one_shot"] = bool(d["one_shot"])
    return WebhookRow(**{k: d[k] for k in WebhookRow.model_fields})


@router.get("/webhooks", response_model=list[WebhookRow])
def list_webhooks(user_id: int = Depends(get_current_user_id)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM webhooks WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
    return [_row_to_model(r) for r in rows]


@router.post("/webhooks", response_model=WebhookRow, status_code=201)
async def create_webhook(req: WebhookCreate, user_id: int = Depends(get_current_user_id)):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO webhooks "
            "(user_id, url, event_type, symbol, target_cents, direction, metric, enabled, one_shot) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, req.url, req.event_type, req.symbol, req.target_cents,
                req.direction, req.metric, int(req.enabled), int(req.one_shot),
            ),
        )
        row = conn.execute("SELECT * FROM webhooks WHERE id = ?", (cur.lastrowid,)).fetchone()
    # Subscribe a new price/portfolio rule's symbol immediately (don't wait for the watcher).
    await webhooks.reconcile_subscriptions()
    return _row_to_model(row)


@router.put("/webhooks/{webhook_id}", response_model=WebhookRow)
async def update_webhook(
    webhook_id: int, req: WebhookUpdate, user_id: int = Depends(get_current_user_id)
):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE webhooks SET enabled = ? WHERE id = ? AND user_id = ?",
            (int(req.enabled), webhook_id, user_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="webhook not found")
        row = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
    await webhooks.reconcile_subscriptions()
    return _row_to_model(row)


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: int, user_id: int = Depends(get_current_user_id)):
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="webhook not found")
    await webhooks.reconcile_subscriptions()
