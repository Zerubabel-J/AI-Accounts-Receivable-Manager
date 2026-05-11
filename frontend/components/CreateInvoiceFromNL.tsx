"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiRaw } from "@/lib/api";
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
  email?: string | null;
  customer_name?: string | null;
}

interface NLResponse {
  invoice: Invoice;
  extracted: Extracted;
  reasoning: string;
}

interface SimulateResult {
  payment_id: string;
  match_status: string;
  confidence: number;
  reasoning: string;
  method: string;
  invoice_id: string | null;
}

interface NeedsMore {
  needs: string;
  extracted: Extracted;
  message: string;
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

  // Follow-up email flow when Gemini couldn't find a client email
  const [followUp, setFollowUp] = useState<NeedsMore | null>(null);
  const [email, setEmail] = useState("");

  // Pay-specific demo flow
  const [paying, setPaying] = useState(false);
  const [paid, setPaid] = useState<SimulateResult | null>(null);

  async function submit(emailOverride?: string) {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { ok, status, data } = await apiRaw<NLResponse | NeedsMore>(
        "/invoices/from-nl",
        {
          method: "POST",
          body: JSON.stringify({ text, email: emailOverride ?? null }),
        },
      );

      if (ok) {
        const success = data as NLResponse;
        setLast(success);
        setFollowUp(null);
        setEmail("");
        setText("");
        setPaid(null);
        router.refresh();
        return;
      }

      if (status === 422 && (data as NeedsMore).needs === "email") {
        setFollowUp(data as NeedsMore);
        return;
      }

      const err = data as { detail?: string };
      setError(err.detail || `Request failed (${status})`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function continueWithEmail() {
    if (!email.trim()) return;
    await submit(email.trim());
  }

  function reset() {
    setFollowUp(null);
    setEmail("");
    setText("");
  }

  async function payThisInvoice() {
    if (!last) return;
    setPaying(true);
    try {
      const { ok, data } = await apiRaw<SimulateResult>("/payments/simulate", {
        method: "POST",
        body: JSON.stringify({
          scenario: "pay_specific",
          invoice_id: last.invoice.invoice_id,
        }),
      });
      if (ok) {
        setPaid(data);
        router.refresh();
      } else {
        setError(
          (data as unknown as { detail?: string }).detail ||
            "Pay failed - the invoice may already be paid",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPaying(false);
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

      {!followUp ? (
        <>
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
              onClick={() => submit()}
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
        </>
      ) : (
        <div className="mt-4 rounded-md bg-white p-4 ring-1 ring-violet-200">
          <div className="text-sm">
            <div className="font-medium text-violet-900">{followUp.message}</div>
            <div className="mt-2 text-xs text-slate-500">
              Original request:{" "}
              <span className="italic text-slate-700">&ldquo;{text}&rdquo;</span>
            </div>
          </div>

          <div className="mt-3 flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && continueWithEmail()}
              placeholder={`billing@${(followUp.extracted.business_name || "client").toLowerCase().replace(/\s+/g, "")}.com`}
              disabled={busy}
              autoFocus
              className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
            />
            <button
              onClick={continueWithEmail}
              disabled={busy || !email.trim()}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50"
            >
              {busy ? "Creating..." : "Continue"}
            </button>
            <button
              onClick={reset}
              disabled={busy}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 sm:grid-cols-4">
            <ExtractedField label="Business" value={followUp.extracted.business_name} />
            <ExtractedField label="Amount" value={`$${followUp.extracted.amount?.toLocaleString()}`} />
            <ExtractedField label="Due" value={followUp.extracted.due_date} />
            <ExtractedField label="Description" value={followUp.extracted.description} />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</div>
      )}

      {last && !error && !followUp && (
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

          {/* Pay-this-invoice action: closes the demo loop */}
          {!paid ? (
            <div className="mt-3 flex items-center justify-between gap-3 rounded-md bg-slate-50 px-3 py-2">
              <span className="text-xs text-slate-600">
                Simulate the client paying this invoice (fires a Stripe-style event into Smart Match)
              </span>
              <button
                onClick={payThisInvoice}
                disabled={paying}
                className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {paying ? "Matching..." : `Pay ${last.invoice.invoice_id}`}
              </button>
            </div>
          ) : (
            <div className="mt-3 rounded-md bg-emerald-50 p-3 ring-1 ring-emerald-200">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-emerald-900">
                  Paid - matched by Smart Match
                </span>
                <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                  {Math.round(paid.confidence * 100)}% via {paid.method}
                </span>
              </div>
              <div className="mt-1 text-xs text-emerald-800">{paid.reasoning}</div>
            </div>
          )}
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
