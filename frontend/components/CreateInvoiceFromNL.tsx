"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { fmtMoney } from "@/lib/format";

interface Invoice {
  invoice_id: string;
  business_name: string;
  amount: number;
  due_date: string;
}

interface Extracted {
  business_name?: string;
  amount?: number;
  description?: string;
  due_date?: string;
}

interface NLResponse {
  invoice: Invoice;
  extracted: Extracted;
  reasoning: string;
}

const EXAMPLES = [
  "Create an invoice for $2,000 for Acme Corp for the May SEO project, due in 30 days",
  "Bill TechFlow $8,500 for the Q2 mobile app rebuild, net 45",
  "Polaris Studio - $3,750 for brand guidelines, due May 25",
];

export function CreateInvoiceFromNL() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<NLResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api<NLResponse>("/invoices/from-nl", {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setLast(result);
      setText("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border bg-gradient-to-br from-violet-50 via-white to-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">Create an invoice by talking</h2>
          <p className="mt-1 text-xs text-slate-500">
            Type what you want. Gemini extracts client, amount, due date - the agent writes the row.
          </p>
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="e.g. Invoice Acme Corp $2,000 for May SEO, due in 30 days"
          disabled={busy}
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={busy || !text.trim()}
          className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50"
        >
          {busy ? "Thinking..." : "Create"}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            onClick={() => setText(ex)}
            disabled={busy}
            className="rounded-md border border-slate-200 bg-white/60 px-2.5 py-1 text-xs text-slate-600 transition hover:border-violet-300 hover:bg-violet-50"
          >
            {ex.slice(0, 48)}...
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</div>
      )}

      {last && !error && (
        <div className="mt-4 rounded-md bg-white p-3 ring-1 ring-violet-100">
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm">
              <div className="font-medium text-violet-900">
                Created {last.invoice.invoice_id}
              </div>
              <div className="mt-1 text-slate-700">{last.reasoning}</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold tabular-nums">
                {fmtMoney(last.invoice.amount)}
              </div>
              <div className="text-xs text-slate-500">due {last.invoice.due_date}</div>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 sm:grid-cols-4">
            <ExtractedField label="Business" value={last.extracted.business_name} />
            <ExtractedField label="Amount" value={`$${last.extracted.amount?.toLocaleString()}`} />
            <ExtractedField label="Due" value={last.extracted.due_date} />
            <ExtractedField label="Description" value={last.extracted.description} />
          </div>
        </div>
      )}
    </div>
  );
}

function ExtractedField({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <div className="font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 truncate text-slate-700">{value || "-"}</div>
    </div>
  );
}
