// Money / number / date formatting helpers used across screens.

export function fmtMoney(value: number, opts?: { compact?: boolean }): string {
  if (opts?.compact && Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}K`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function daysBetween(isoFrom: string, isoTo: string = new Date().toISOString()): number {
  const a = new Date(isoFrom).getTime();
  const b = new Date(isoTo).getTime();
  return Math.round((b - a) / (1000 * 60 * 60 * 24));
}

export function relativeDays(iso: string): string {
  const days = daysBetween(iso);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  if (days > 0) return `${days} days ago`;
  return `${Math.abs(days)} days from now`;
}
