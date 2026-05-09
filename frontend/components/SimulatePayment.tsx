"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

type Scenario = "clean_match" | "fuzzy_match" | "no_match";

interface SimulateResult {
  payment_id: string;
  scenario: Scenario;
  match_status: string;
  confidence: number;
  reasoning: string;
  method: string;
  invoice_id: string | null;
}

const SCENARIO_LABEL: Record<Scenario, string> = {
  clean_match: "Clean match",
  fuzzy_match: "Fuzzy match",
  no_match: "Unknown payer",
};

export function SimulatePayment() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<SimulateResult | null>(null);

  async function fire(scenario: Scenario) {
    setBusy(true);
    try {
      const result = await api<SimulateResult>("/payments/simulate", {
        method: "POST",
        body: JSON.stringify({ scenario }),
      });
      setLast(result);
      router.refresh();
    } catch (err) {
      alert(`Simulate failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">Simulate a payment</h2>
          <p className="mt-1 text-xs text-slate-500">
            Demo only - fires a fake Stripe-style payment so you can watch Smart Match decide live.
          </p>
        </div>
        <div className="flex gap-2">
          {(Object.keys(SCENARIO_LABEL) as Scenario[]).map((s) => (
            <button
              key={s}
              disabled={busy}
              onClick={() => fire(s)}
              className="rounded-md border bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {SCENARIO_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      {last && (
        <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-slate-500">{last.payment_id}</span>
            <ResultBadge status={last.match_status} />
            <span className="text-xs text-slate-500">via {last.method}</span>
          </div>
          <div className="mt-1 text-slate-700">{last.reasoning}</div>
        </div>
      )}
    </div>
  );
}

function ResultBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    confirmed: "bg-emerald-100 text-emerald-800",
    needs_review: "bg-amber-100 text-amber-800",
    no_match: "bg-slate-100 text-slate-700",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[status] ?? "bg-slate-100"}`}>
      {status.replace("_", " ")}
    </span>
  );
}
