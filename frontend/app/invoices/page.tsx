import { PayInvoiceButton } from "@/components/PayInvoiceButton";
import { InvoiceStatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { fmtDate, fmtMoney } from "@/lib/format";
import type { Invoice } from "@/lib/types";

async function loadInvoices(): Promise<Invoice[] | null> {
  try {
    return await api<Invoice[]>("/invoices");
  } catch (err) {
    console.error("invoices fetch failed", err);
    return null;
  }
}

export default async function InvoicesPage() {
  const invoices = await loadInvoices();

  if (!invoices) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center text-slate-600">
        Backend unreachable.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
        <p className="mt-1 text-sm text-slate-500">
          {invoices.length} invoices — sortable by status, amount, or due date.
        </p>
      </header>

      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Invoice</th>
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Business</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 text-right font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Due</th>
              <th className="px-4 py-3 text-right font-medium">Risk</th>
              <th className="px-4 py-3 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {invoices.map((inv) => (
              <tr key={inv.invoice_id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{inv.invoice_id}</td>
                <td className="px-4 py-3">{inv.customer_name}</td>
                <td className="px-4 py-3 text-slate-600">{inv.business_name}</td>
                <td className="px-4 py-3">
                  <InvoiceStatusBadge status={inv.status} />
                </td>
                <td className="px-4 py-3 text-right font-medium tabular-nums">
                  {fmtMoney(inv.amount)}
                </td>
                <td className="px-4 py-3 text-slate-600">{fmtDate(inv.due_date)}</td>
                <td className="px-4 py-3 text-right">
                  {inv.risk_score >= 70 ? (
                    <span
                      className="inline-flex items-center rounded-md bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-800"
                      title={inv.risk_reason}
                    >
                      {inv.risk_score}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <PayInvoiceButton
                    invoiceId={inv.invoice_id}
                    enabled={inv.status === "sent" || inv.status === "overdue"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
