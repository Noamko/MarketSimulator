from fastapi import APIRouter

from ..db import get_conn
from ..models import Portfolio
from ..portfolio import snapshot
from ..price_hub import hub

router = APIRouter()


@router.get("/portfolio", response_model=Portfolio)
def get_portfolio() -> Portfolio:
    with get_conn() as conn:
        return snapshot(conn, hub)
