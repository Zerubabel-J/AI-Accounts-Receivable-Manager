import Link from "next/link";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { CreateInvoiceFromNL } from "@/components/CreateInvoiceFromNL";
import { SimulatePayment } from "@/components/SimulatePayment";
import { StatCard } from "@/components/StatCard";
import { MatchStatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { fmtMoney, relativeDays } from "@/lib/format";
import type { DashboardStats, Payment } from "@/lib/types";

async function loadData(): Promise<{ stats: DashboardStats; review: Payment[] } | null> {
  try {
    const [stats, review] = await Promise.all([
      api<DashboardStats>("/stats"),
      api<Payment[]>("/review-queue"),
    ]);
    return { stats, review };
  } catch (err) {
    console.error("Dashboard data fetch failed", err);
    return null;
  }
}

export default async function DashboardPage() {
  const data = await loadData();

  if (!data) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center text-slate-600">
        <p className="text-lg font-medium">Backend unreachable.</p>
        <p className="mt-2 text-sm">
          Start the API: <code className="rounded bg-slate-100 px-1.5 py-0.5">uvicorn app.main:app --reload</code>
        </p>
      </div>
    );
  }

  const { stats, review } = data;
  const dsoDelta = stats.dso_days - stats.dso_target;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your AR at a glance. The agent is watching, matching, and chasing.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Collected (30d)"
          value={fmtMoney(stats.collected_30d)}
          tone="good"
        />
        <StatCard
          label="Outstanding"
          value={fmtMoney(stats.outstanding_total)}
          hint={`${stats.outstanding_count} invoices`}
        />
        <StatCard
          label="Cash at Risk"
          value={fmtMoney(stats.cash_at_risk)}
          hint={`${stats.cash_at_risk_count} flagged`}
          tone="bad"
        />
        <StatCard
          label="DSO"
          value={`${stats.dso_days} days`}
          hint={
            dsoDelta === 0
              ? `on target (${stats.dso_target}d)`
              : dsoDelta > 0
                ? `${dsoDelta}d over target`
                : `${Math.abs(dsoDelta)}d under target`
          }
          tone={dsoDelta > 0 ? "warn" : "good"}
        />
      </section>

      <CreateInvoiceFromNL />

      <SimulatePayment />

      <section className="rounded-lg border bg-gradient-to-r from-emerald-50 to-white p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium uppercase tracking-wide text-emerald-700">
              Recovered Revenue (this month)
            </div>
            <div className="mt-1 text-3xl font-semibold text-emerald-900">
              {fmtMoney(stats.recovered_revenue_mtd)}
            </div>
          </div>
          <div className="max-w-md text-right text-xs text-emerald-800">
            Money brought in this month from invoices the agent matched and chased.
            Without this you would be reconciling on Sunday night.
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border bg-white">
          <div className="flex items-center justify-between border-b px-5 py-3">
            <h2 className="text-sm font-semibold">Needs Your Review</h2>
            <Link href="/review" className="text-xs text-blue-600 hover:underline">
              View all →
            </Link>
          </div>
          <ul className="divide-y">
            {review.slice(0, 5).map((p) => (
              <li key={p.payment_id} className="px-5 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{p.payer_name || p.payer_email}</span>
                      <MatchStatusBadge status={p.match_status} />
                    </div>
                    <div className="mt-1 truncate text-xs text-slate-500">{p.match_reasoning}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold tabular-nums">{fmtMoney(p.amount)}</div>
                    <div className="text-xs text-slate-500">{relativeDays(p.received_at)}</div>
                  </div>
                </div>
                <div className="mt-2">
                  <ConfidenceBar value={p.match_confidence} />
                </div>
              </li>
            ))}
            {review.length === 0 && (
              <li className="px-5 py-8 text-center text-sm text-slate-500">
                Nothing in the queue. Agent is caught up.
              </li>
            )}
          </ul>
        </div>

        <div className="rounded-lg border bg-white">
          <div className="border-b px-5 py-3">
            <h2 className="text-sm font-semibold">High-Risk Clients</h2>
          </div>
          <ul className="divide-y">
            {stats.high_risk_clients.map((c) => (
              <li key={c.email} className="px-5 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{c.business_name}</div>
                    <div className="mt-0.5 truncate text-xs text-slate-500">{c.reason}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold tabular-nums text-rose-700">
                      {fmtMoney(c.outstanding)}
                    </div>
                    <div className="text-xs text-slate-500">risk {c.risk_score}</div>
                  </div>
                </div>
              </li>
            ))}
            {stats.high_risk_clients.length === 0 && (
              <li className="px-5 py-8 text-center text-sm text-slate-500">
                No high-risk clients flagged.
              </li>
            )}
          </ul>
        </div>
      </section>
    </div>
  );
}
