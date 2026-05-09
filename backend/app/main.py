import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.integrations.sheets import get_store
from app.routers import invoices, jobs, payments, review, stats, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.seed_on_startup:
        store = get_store()
        if not store.list_invoices():
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
            from seed import seed_demo_data  # type: ignore[import-not-found]

            summary = seed_demo_data(verbose=False)
            log.info(
                "Seeded demo data: %d invoices, %d payments, $%.0f outstanding",
                summary["invoices"],
                summary["payments"],
                summary["outstanding"],
            )
    yield


app = FastAPI(
    title="AI Accounts Receivable Manager",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(review.router)
app.include_router(stats.router)
app.include_router(webhooks.router)
app.include_router(jobs.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
