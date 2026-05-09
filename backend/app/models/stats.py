from pydantic import BaseModel


class HighRiskClient(BaseModel):
    business_name: str
    email: str
    risk_score: int
    reason: str
    outstanding: float


class DashboardStats(BaseModel):
    collected_30d: float
    outstanding_total: float
    outstanding_count: int
    cash_at_risk: float
    cash_at_risk_count: int
    dso_days: int
    dso_target: int
    needs_review_count: int
    recovered_revenue_mtd: float
    high_risk_clients: list[HighRiskClient]
