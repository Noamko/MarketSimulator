from fastapi import APIRouter, Depends

from ..db import get_conn
from ..models import Portfolio
from ..portfolio import snapshot
from ..price_hub import hub
from ..users import get_current_user_id

router = APIRouter()


@router.get("/portfolio", response_model=Portfolio)
def get_portfolio(user_id: int = Depends(get_current_user_id)) -> Portfolio:
    with get_conn() as conn:
        return snapshot(conn, hub, user_id)
