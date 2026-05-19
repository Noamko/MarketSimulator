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
