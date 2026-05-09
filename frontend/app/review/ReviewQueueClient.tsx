"use client";

import { useState } from "react";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { api } from "@/lib/api";
import { fmtDate, fmtMoney, relativeDays } from "@/lib/format";
import type { Invoice, Payment } from "@/lib/types";

interface Props {
  initialPayments: Payment[];
  invoices: Invoice[];
}

export function ReviewQueueClient({ initialPayments, invoices }: Props) {
  const [items, setItems] = useState(initialPayments);
  const [busyId, setBusyId] = useState<string | null>(null);

  const invById = new Map(invoices.map((i) => [i.invoice_id, i]));

  async function approve(p: Payment) {
    setBusyId(p.payment_id);
    try {
      await api<Payment>(`/review-queue/${p.payment_id}/approve`, { method: "POST" });
      setItems((prev) => prev.filter((x) => x.payment_id !== p.payment_id));
    } catch (err) {
      alert(`Approve failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function reject(p: Payment) {
    setBusyId(p.payment_id);
    try {
      await api<Payment>(`/review-queue/${p.payment_id}/reject`, { method: "POST" });
      setItems((prev) => prev.filter((x) => x.payment_id !== p.payment_id));
    } catch (err) {
      alert(`Reject failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBusyId(null);
    }
  }

  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-white p-12 text-center">
        <div className="text-lg font-medium">All clear.</div>
        <div className="mt-2 text-sm text-slate-500">
          The agent has nothing for you to review right now.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {items.map((p) => {
        const inv = p.matched_invoice_id ? invById.get(p.matched_invoice_id) : null;
        return (
          <div key={p.payment_id} className="rounded-lg border bg-white p-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Incoming payment
                </div>
                <div className="mt-2 space-y-1">
                  <div className="font-medium">{p.payer_name || "(no name)"}</div>
                  <div className="text-sm text-slate-600">{p.payer_email}</div>
                  <div className="text-2xl font-semibold tabular-nums">{fmtMoney(p.amount)}</div>
                  <div className="text-xs text-slate-500">{relativeDays(p.received_at)}</div>
                </div>
              </div>

              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Candidate invoice
                </div>
                {inv ? (
                  <div className="mt-2 space-y-1">
                    <div className="font-medium">
                      {inv.customer_name}
                      <span className="ml-2 font-mono text-xs text-slate-500">
                        {inv.invoice_id}
                      </span>
                    </div>
                    <div className="text-sm text-slate-600">{inv.business_name || inv.email}</div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {fmtMoney(inv.amount)}
                    </div>
                    <div className="text-xs text-slate-500">due {fmtDate(inv.due_date)}</div>
                  </div>
                ) : (
                  <div className="mt-2 text-sm text-slate-500">No candidate selected.</div>
                )}
              </div>
            </div>

            <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                AI reasoning
              </div>
              <div className="mt-1 text-slate-700">{p.match_reasoning}</div>
              <div className="mt-2">
                <ConfidenceBar value={p.match_confidence} />
              </div>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                disabled={busyId === p.payment_id}
                onClick={() => reject(p)}
                className="rounded-md border bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                disabled={busyId === p.payment_id || !inv}
                onClick={() => approve(p)}
                className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                Approve match
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
