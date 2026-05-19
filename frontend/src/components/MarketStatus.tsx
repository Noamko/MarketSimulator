interface Props {
  open: boolean;
  connected: boolean;
}

export function MarketStatus({ open, connected }: Props) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <span className={`market-status ${open ? "open" : "closed"}`}>
        {open ? "● Market open" : "○ Market closed"}
      </span>
      <span className="market-status" style={{ color: connected ? "var(--green)" : "var(--muted)" }}>
        {connected ? "WS connected" : "WS disconnected"}
      </span>
    </div>
  );
}
