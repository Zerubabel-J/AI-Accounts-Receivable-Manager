import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "good" | "warn" | "bad";
}

const TONE: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-slate-900",
  good: "text-emerald-700",
  warn: "text-amber-700",
  bad: "text-rose-700",
};

export function StatCard({ label, value, hint, tone = "default" }: StatCardProps) {
  return (
    <div className="rounded-lg border bg-white p-5">
      <div className="text-sm font-medium text-slate-500">{label}</div>
      <div className={cn("mt-2 text-3xl font-semibold tracking-tight tabular-nums", TONE[tone])}>
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}
