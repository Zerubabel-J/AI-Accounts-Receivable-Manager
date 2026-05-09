import { ReviewQueueClient } from "./ReviewQueueClient";
import { api } from "@/lib/api";
import type { Invoice, Payment } from "@/lib/types";

async function loadData(): Promise<{ payments: Payment[]; invoices: Invoice[] } | null> {
  try {
    const [payments, invoices] = await Promise.all([
      api<Payment[]>("/review-queue"),
      api<Invoice[]>("/invoices"),
    ]);
    return { payments, invoices };
  } catch (err) {
    console.error("review queue fetch failed", err);
    return null;
  }
}

export default async function ReviewQueuePage() {
  const data = await loadData();

  if (!data) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center text-slate-600">
        Backend unreachable.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Review Queue</h1>
        <p className="mt-1 text-sm text-slate-500">
          {data.payments.length} payments need your call. The agent matched them but it is not
          confident enough to mark them paid on its own.
        </p>
      </header>
      <ReviewQueueClient initialPayments={data.payments} invoices={data.invoices} />
    </div>
  );
}
