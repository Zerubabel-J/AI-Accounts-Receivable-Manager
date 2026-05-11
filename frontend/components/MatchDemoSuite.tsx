"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiRaw } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import type { Invoice } from "@/lib/types";

interface PayResult {
  payment_id: string;
  invoice_id: string | null;
  match_status: string;
  confidence: number;
  reasoning: string;
  method: string;
  payer_name: string;
  payer_email: string;
  amount: number;
}

type Scenario = "exact" | "fuzzy" | "smart" | "no_match";

const SCENARIOS: { id: Scenario; label: string; emoji: string; note: string }[] = [
  {
    id: "exact",
    label: "Exact match",
    emoji: "🟢",
    note: "Payer email and amount match the invoice exactly. Smart Match confirms via the email path.",
  },
  {
    id: "fuzzy",
    label: "Fuzzy match",
    emoji: "🟡",
    note: "Different email but business name matches (after normalizing LLC/Inc). Confirms via business path.",
  },
  {
    id: "smart",
    label: "Smart match (Gemini)",
    emoji: "🟣",
    note: "Garbled name and an alias email. Gemini has to reason about whether the payer is the same entity.",
  },
  {
    id: "no_match",
    label: "Unknown payer",
    emoji: "🔴",
    note: "Totally unknown payer, amount also off. Smart Match should flag it for human review.",
  },
];

/** Build the payload each scenario sends. Mirrors what Stripe's charge.succeeded would deliver. */
function buildPayload(scenario: Scenario, invoice: Invoice) {
  switch (scenario) {
    case "exact":
      return {
        payer_name: invoice.customer_name,
        payer_email: invoice.email,
        amount: invoice.amount,
      };
    case "fuzzy":
      return {
        payer_name: `${invoice.business_name} LLC`,
        payer_email: `ap@${invoice.business_name.toLowerCase().replace(/\s+/g, "")}.com`,
        amount: invoice.amount,
      };
    case "smart":
      return {
        payer_name: invoice.business_name.split(" ")[0],
        payer_email: `accounting+${invoice.business_name.toLowerCase().replace(/\s+/g, "").slice(0, 6)}@gmail.com`,
        amount: invoice.amount,
      };
    case "no_match":
      return {
        payer_name: "Unknown Buyer Co",
        payer_email: "ap@randomcorp.example",
        amount: Math.round(invoice.amount * 1.7), // way off
      };
  }
}

const STATUS_STYLES: Record<string, string> = {
  confirmed: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  needs_review: "bg-amber-100 text-amber-800 ring-amber-200",
  no_match: "bg-rose-100 text-rose-800 ring-rose-200",
};

export function MatchDemoSuite({ invoices }: { invoices: Invoice[] }) {
  const router = useRouter();
  const openInvoices = invoices.filter(
    (i) => i.status === "sent" || i.status === "overdue",
  );
  const [selectedId, setSelectedId] = useState<string>(openInvoices[0]?.invoice_id ?? "");
  const selected = openInvoices.find((i) => i.invoice_id === selectedId) ?? openInvoices[0];

  const [busy, setBusy] = useState<Scenario | null>(null);
  const [result, setResult] = useState<{ scenario: Scenario; payload: object; result?: PayResult; error?: string } | null>(null);

  async function fire(scenario: Scenario) {
    if (!selected) return;
    const payload = buildPayload(scenario, selected);
    setBusy(scenario);
    setResult({ scenario, payload });

    try {
      const { ok, data } = await apiRaw<PayResult>(
        `/invoices/${selected.invoice_id}/pay`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      if (ok) {
        setResult({ scenario, payload, result: data });
        router.refresh();
      } else {
        setResult({
          scenario,
          payload,
          error:
            (data as unknown as { detail?: string }).detail ||
            "Request failed",
        });
      }
    } catch (err) {
      setResult({ scenario, payload, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(null);
    }
  }

  if (!selected) {
    return (
      <div className="rounded-lg border bg-white p-5 text-sm text-slate-500">
        No open invoices available to test Smart Match against.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-gradient-to-br from-slate-50 via-white to-white p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold">Match Demo Suite</h2>
        <p className="text-xs text-slate-500">
          Pick an invoice, then fire one of four Stripe-shaped payloads. Each exercises a different
          Smart Match path. The exact payload sent and the result land below side by side.
        </p>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <label className="text-xs font-medium text-slate-600">Target invoice:</label>
        <select
          value={selectedId}
          onChange={(e) => {
            setSelectedId(e.target.value);
            setResult(null);
          }}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        >
          {openInvoices.map((i) => (
            <option key={i.invoice_id} value={i.invoice_id}>
              {i.invoice_id} - {i.business_name} ({fmtMoney(i.amount)})
            </option>
          ))}
        </select>
        <span className="text-xs text-slate-500">
          email: <span className="font-mono">{selected.email}</span>
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => fire(s.id)}
            disabled={busy !== null}
            title={s.note}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50"
          >
            <div className="flex items-center gap-2">
              <span>{s.emoji}</span>
              <span>{s.label}</span>
            </div>
            <div className="mt-0.5 text-xs font-normal text-slate-500">
              {busy === s.id ? "Running..." : "Click to fire"}
            </div>
          </button>
        ))}
      </div>

      {result && (
        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {/* Left: payload sent */}
          <div className="rounded-md bg-slate-900 p-3 font-mono text-xs text-slate-100">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Payload sent ({result.scenario})
            </div>
            <pre className="whitespace-pre-wrap">
              POST /invoices/{selected.invoice_id}/pay{"\n"}
              {JSON.stringify(result.payload, null, 2)}
            </pre>
          </div>

          {/* Right: result */}
          <div className="rounded-md border bg-white p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Smart Match result
            </div>
            {result.error && (
              <div className="rounded-md bg-rose-50 p-2 text-sm text-rose-800">{result.error}</div>
            )}
            {result.result && (
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_STYLES[result.result.match_status] ?? "bg-slate-100 text-slate-700"}`}
                  >
                    {result.result.match_status.replace("_", " ")}
                  </span>
                  <span className="text-xs text-slate-500">
                    via {result.result.method} - {Math.round(result.result.confidence * 100)}%
                  </span>
                </div>
                <div className="text-slate-700">{result.result.reasoning}</div>
                {result.result.invoice_id && (
                  <div className="text-xs text-slate-500">
                    Matched to{" "}
                    <span className="font-mono">{result.result.invoice_id}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
