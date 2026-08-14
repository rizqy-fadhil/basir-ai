"""Basir AI FastAPI application entry point.

Registers all API routers and configures global exception handling.
Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
def health() -> dict:
    """Simple liveness probe."""
    return {"status": "ok"}
