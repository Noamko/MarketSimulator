CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    cash_cents  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    symbol              TEXT    NOT NULL,
    side                TEXT    NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    price_cents         INTEGER NOT NULL,
    executed_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    realized_pnl_cents  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_trades_user      ON trades(user_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_symbol    ON trades(symbol);

CREATE TABLE IF NOT EXISTS lots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    symbol              TEXT    NOT NULL,
    quantity_remaining  INTEGER NOT NULL CHECK (quantity_remaining > 0),
    cost_basis_cents    INTEGER NOT NULL,
    opened_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    trade_id            INTEGER NOT NULL REFERENCES trades(id)
);
CREATE INDEX IF NOT EXISTS idx_lots_user_symbol ON lots(user_id, symbol, opened_at);

CREATE TABLE IF NOT EXISTS webhooks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id),
    url              TEXT    NOT NULL,
    event_type       TEXT    NOT NULL CHECK (event_type IN
                         ('PRICE_TARGET','MARKET_STATUS','TRADE_EXECUTED','PORTFOLIO_THRESHOLD')),
    symbol           TEXT,                                              -- PRICE_TARGET only
    target_cents     INTEGER,                                           -- price / equity / pnl threshold
    direction        TEXT CHECK (direction IN ('above','below')),       -- PRICE_TARGET & PORTFOLIO_THRESHOLD
    metric           TEXT CHECK (metric IN ('equity','realized_pnl')),  -- PORTFOLIO_THRESHOLD only
    enabled          INTEGER NOT NULL DEFAULT 1,
    one_shot         INTEGER NOT NULL DEFAULT 1,
    last_value_cents INTEGER,                                           -- crossing-detection baseline
    last_fired_at    TEXT,
    created_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_webhooks_user   ON webhooks(user_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_active ON webhooks(enabled, event_type, symbol);
