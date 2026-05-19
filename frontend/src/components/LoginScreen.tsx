import { useEffect, useState } from "react";
import type { User } from "../types";
import { createUser, listUsers } from "../api";
import { fmtMoney } from "../format";

interface Props {
  onPick: (user: User) => void;
}

export function LoginScreen({ onPick }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [mode, setMode] = useState<"pick" | "create">("pick");
  const [name, setName] = useState("");
  const [cashDollars, setCashDollars] = useState("100000");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    setLoadingList(true);
    listUsers()
      .then((list) => { setUsers(list); if (list.length === 0) setMode("create"); })
      .catch((e) => setError(e?.message ?? String(e)))
      .finally(() => setLoadingList(false));
  };

  useEffect(refresh, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cents = Math.round(parseFloat(cashDollars) * 100);
      if (!Number.isFinite(cents) || cents < 0) throw new Error("starting cash must be a non-negative number");
      const user = await createUser(name.trim(), cents);
      onPick(user);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1>MarketSimulator</h1>
        <p className="muted">Pick an existing user or create a new one. No password — names just identify which portfolio you're playing with.</p>

        {mode === "pick" && (
          <>
            <h2>Sign in</h2>
            {loadingList && <div className="muted">Loading…</div>}
            {!loadingList && users.length === 0 && (
              <div className="muted">No users yet — create one to start.</div>
            )}
            {users.map((u) => (
              <button
                key={u.id}
                type="button"
                className="user-row"
                onClick={() => onPick(u)}
              >
                <span className="user-name">{u.name}</span>
                <span className="muted">cash {fmtMoney(u.cash_cents)}</span>
              </button>
            ))}
            <div className="login-actions">
              <button type="button" onClick={() => { setMode("create"); setError(null); }}>
                + New user
              </button>
            </div>
          </>
        )}

        {mode === "create" && (
          <>
            <h2>Create a user</h2>
            <form onSubmit={submit} className="create-form">
              <label>
                <span>Name (unique)</span>
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. noam"
                  maxLength={40}
                  required
                />
              </label>
              <label>
                <span>Starting cash ($)</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={cashDollars}
                  onChange={(e) => setCashDollars(e.target.value)}
                  required
                />
              </label>
              <div className="login-actions">
                {users.length > 0 && (
                  <button type="button" onClick={() => { setMode("pick"); setError(null); }}>
                    Cancel
                  </button>
                )}
                <button type="submit" disabled={busy || !name.trim()}>
                  {busy ? "Creating…" : "Create & sign in"}
                </button>
              </div>
            </form>
          </>
        )}

        {error && <div className="login-error">{error}</div>}
      </div>
    </div>
  );
}
