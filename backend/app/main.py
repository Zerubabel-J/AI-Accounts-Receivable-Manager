import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import invoices, jobs, payments, review, stats, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="AI Accounts Receivable Manager",
    version="0.1.0",
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
