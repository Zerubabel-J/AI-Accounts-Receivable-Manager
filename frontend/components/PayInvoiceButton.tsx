"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiRaw } from "@/lib/api";

interface SimulateResult {
  match_status: string;
  confidence: number;
  reasoning: string;
  method: string;
}

interface Props {
  invoiceId: string;
  /** Only render the button when the invoice is in an open status. */
  enabled: boolean;
}

export function PayInvoiceButton({ invoiceId, enabled }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SimulateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function fire() {
    setBusy(true);
    setError(null);
    try {
      const { ok, data } = await apiRaw<SimulateResult>(
        `/invoices/${invoiceId}/pay`,
        { method: "POST" },
      );
      if (ok) {
        setResult(data);
        router.refresh();
      } else {
        setError(
          (data as unknown as { detail?: string }).detail || "Pay failed",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!enabled) {
    return <span className="text-xs text-slate-400">-</span>;
  }

  if (result) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
        title={result.reasoning}
      >
        Paid - {Math.round(result.confidence * 100)}%
      </span>
    );
  }

  if (error) {
    return (
      <span
        className="inline-flex items-center rounded-md bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-800"
        title={error}
      >
        Error
      </span>
    );
  }

  return (
    <button
      onClick={fire}
      disabled={busy}
      className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-800 disabled:opacity-50"
    >
      {busy ? "Paying..." : "Simulate payment"}
    </button>
  );
}
