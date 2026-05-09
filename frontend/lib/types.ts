// Mirror of the backend pydantic models. Keep these in sync by hand for now.

export type InvoiceStatus = "sent" | "overdue" | "paid" | "at_risk";
export type MatchStatus = "confirmed" | "needs_review" | "no_match";
export type MatchMethod = "exact_email" | "exact_business" | "fuzzy_ai" | "none";
export type PaymentSource = "stripe" | "manual";

export interface Invoice {
  invoice_id: string;
  customer_name: string;
  business_name: string;
  email: string;
  phone: string;
  amount: number;
  issued_date: string;
  due_date: string;
  status: InvoiceStatus;
  risk_score: number;
  risk_reason: string;
  reminder_count: number;
  last_reminder_at: string | null;
  paid_at: string | null;
  matched_payment_id: string | null;
}

export interface Payment {
  payment_id: string;
  source: PaymentSource;
  payer_name: string;
  payer_email: string;
  amount: number;
  received_at: string;
  matched_invoice_id: string | null;
  match_confidence: number;
  match_reasoning: string;
  match_status: MatchStatus;
  reviewed_by_user: boolean;
}

export interface HighRiskClient {
  business_name: string;
  email: string;
  risk_score: number;
  reason: string;
  outstanding: number;
}

export interface DashboardStats {
  collected_30d: number;
  outstanding_total: number;
  outstanding_count: number;
  cash_at_risk: number;
  cash_at_risk_count: number;
  dso_days: number;
  dso_target: number;
  needs_review_count: number;
  recovered_revenue_mtd: number;
  high_risk_clients: HighRiskClient[];
}
