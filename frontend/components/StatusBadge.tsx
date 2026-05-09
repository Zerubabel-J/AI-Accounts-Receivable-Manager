import { cn } from "@/lib/utils";
import type { InvoiceStatus, MatchStatus } from "@/lib/types";

const INVOICE_STYLES: Record<InvoiceStatus, string> = {
  sent: "bg-amber-100 text-amber-800 ring-amber-600/20",
  overdue: "bg-blue-100 text-blue-800 ring-blue-600/20",
  paid: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  at_risk: "bg-rose-100 text-rose-800 ring-rose-600/20",
};

const INVOICE_LABEL: Record<InvoiceStatus, string> = {
  sent: "Sent",
  overdue: "Overdue",
  paid: "Paid",
  at_risk: "At Risk",
};

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        INVOICE_STYLES[status],
      )}
    >
      {INVOICE_LABEL[status]}
    </span>
  );
}

const MATCH_STYLES: Record<MatchStatus, string> = {
  confirmed: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  needs_review: "bg-amber-100 text-amber-800 ring-amber-600/20",
  no_match: "bg-slate-100 text-slate-700 ring-slate-600/20",
};

const MATCH_LABEL: Record<MatchStatus, string> = {
  confirmed: "Confirmed",
  needs_review: "Needs Review",
  no_match: "No Match",
};

export function MatchStatusBadge({ status }: { status: MatchStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        MATCH_STYLES[status],
      )}
    >
      {MATCH_LABEL[status]}
    </span>
  );
}
