from fastapi import APIRouter

from app.integrations.sheets import get_store
from app.models.stats import DashboardStats
from app.services.stats import compute_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=DashboardStats)
def get_stats() -> DashboardStats:
    return compute_stats(get_store())
