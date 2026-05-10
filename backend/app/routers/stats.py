from fastapi import APIRouter

from app.config import settings
from app.integrations.gemini import get_judge
from app.integrations.sheets import GoogleSheetsStore, get_store
from app.models.stats import DashboardStats
from app.services.stats import compute_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=DashboardStats)
def get_stats() -> DashboardStats:
    return compute_stats(get_store())


@router.get("/system-status")
def system_status() -> dict:
    """Tells the UI which integrations are live."""
    store = get_store()
    return {
        "store_backend": "google_sheets" if isinstance(store, GoogleSheetsStore) else "in_memory",
        "sheet_id": settings.google_sheets_id or None,
        "gemini_enabled": get_judge() is not None,
        "send_emails_for_real": settings.send_emails_for_real,
    }
