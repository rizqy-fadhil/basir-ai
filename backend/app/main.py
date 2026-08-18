"""Basir AI FastAPI application entry point.

Registers all API routers and configures global exception handling.
Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.meja import router as meja_router
from app.routers.snapshot import router as snapshot_router
from app.routers.status import cafe_router, internal_router

app = FastAPI(
    title="Basir AI — Backend API",
    description=(
        "REST API untuk monitoring okupansi meja cafe secara real-time. "
        "Inference service mengirim hasil deteksi via POST /internal/status; "
        "frontend polling via GET /cafes/{cafe_id}/status."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Next.js dev server in local mode
# ---------------------------------------------------------------------------
# allow_origins=["*"] is intentionally permissive for the MVP/demo phase.
# In this context the backend is an internal API (not user-facing auth), and
# the primary consumer is the Next.js dev server on localhost. Judges need to
# run the frontend from arbitrary origins during local evaluation.
# For production, restrict this to the actual frontend domain via an env var
# or reverse-proxy CORS header override.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restricted further in production via env/proxy
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(meja_router)
app.include_router(snapshot_router)
app.include_router(cafe_router)
app.include_router(internal_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"], summary="Health check")
def health(db: Session = Depends(get_db)) -> JSONResponse:
    """Readiness probe: verify that the application can reach the database.

    Executes ``SELECT 1`` against the configured database.  Returns HTTP 200
    when the database responds and HTTP 503 when it does not.  This makes the
    endpoint suitable as a Docker HEALTHCHECK target so the container is only
    marked healthy once the DB connection is confirmed.
    """
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"status": "error", "detail": str(exc)},
            status_code=503,
        )
