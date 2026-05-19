CREATE TABLE IF NOT EXISTS account (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cash_cents  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              TEXT    NOT NULL,
    side                TEXT    NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    price_cents         INTEGER NOT NULL,
    executed_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    realized_pnl_cents  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_trades_symbol      ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);

CREATE TABLE IF NOT EXISTS lots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              TEXT    NOT NULL,
    quantity_remaining  INTEGER NOT NULL CHECK (quantity_remaining > 0),
    cost_basis_cents    INTEGER NOT NULL,
    opened_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    trade_id            INTEGER NOT NULL REFERENCES trades(id)
);
CREATE INDEX IF NOT EXISTS idx_lots_symbol ON lots(symbol, opened_at);
