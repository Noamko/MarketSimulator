from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.strip().upper()


class TradeRow(BaseModel):
    id: int
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    price_cents: int
    executed_at: str
    realized_pnl_cents: Optional[int] = None


class Position(BaseModel):
    symbol: str
    quantity: int
    avg_cost_cents: int
    last_price_cents: Optional[int]
    market_value_cents: Optional[int]
    unrealized_pnl_cents: Optional[int]


class Portfolio(BaseModel):
    cash_cents: int
    positions: list[Position]
    total_realized_pnl_cents: int
    total_equity_cents: int
    market_open: bool


class Quote(BaseModel):
    symbol: str
    price_cents: int
    source: Literal["stream", "rest"]
    timestamp_ms: Optional[int] = None
