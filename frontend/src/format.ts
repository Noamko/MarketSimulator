export function fmtMoney(cents: number | null | undefined): string {
  if (cents == null) return "—";
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}$${dollars.toLocaleString("en-US")}.${rem.toString().padStart(2, "0")}`;
}

export function fmtSignedMoney(cents: number | null | undefined): string {
  if (cents == null) return "—";
  const prefix = cents > 0 ? "+" : "";
  return prefix + fmtMoney(cents);
}

export function fmtPct(numerator: number, denominator: number): string {
  if (!denominator) return "—";
  const pct = (numerator / denominator) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}
