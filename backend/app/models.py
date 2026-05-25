from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

WebhookEvent = Literal[
    "PRICE_TARGET", "MARKET_STATUS", "TRADE_EXECUTED", "PORTFOLIO_THRESHOLD"
]
Direction = Literal["above", "below"]
Metric = Literal["equity", "realized_pnl"]


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


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    event_type: WebhookEvent
    symbol: Optional[str] = Field(default=None, max_length=10)
    target_cents: Optional[int] = None
    direction: Optional[Direction] = None
    metric: Optional[Metric] = None
    enabled: bool = True
    one_shot: bool = True

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v

    @model_validator(mode="after")
    def _check_event_fields(self) -> "WebhookCreate":
        if self.event_type == "PRICE_TARGET":
            if not self.symbol or self.target_cents is None or self.direction is None:
                raise ValueError(
                    "PRICE_TARGET requires symbol, target_cents and direction"
                )
        elif self.event_type == "PORTFOLIO_THRESHOLD":
            if self.metric is None or self.target_cents is None or self.direction is None:
                raise ValueError(
                    "PORTFOLIO_THRESHOLD requires metric, target_cents and direction"
                )
        return self


class WebhookUpdate(BaseModel):
    """Partial update; only `enabled` is editable post-creation (keeps crossing
    state coherent — changing a target would invalidate last_value_cents)."""
    enabled: bool


class WebhookRow(BaseModel):
    id: int
    user_id: int
    url: str
    event_type: WebhookEvent
    symbol: Optional[str] = None
    target_cents: Optional[int] = None
    direction: Optional[str] = None
    metric: Optional[str] = None
    enabled: bool
    one_shot: bool
    last_fired_at: Optional[str] = None
    created_at: str
