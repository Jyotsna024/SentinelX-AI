"""
main.py — SentinelX AI Phase 2 Entrypoint
============================================
FastAPI application core. Configures routers, lifespan startup tasks (Agent 1
model loading, RAG index initialization), and logging infrastructure.

Startup Sequence:
    1. Configure Python logging wrapper.
    2. Add project root to sys.path to allow imports from frozen Phase 1.
    3. Initialize Lifespan:
       - Load Agent 1 (Anomaly Detection Model)
       - Load Agent 2 (RAG Vector Database Index)
    4. Start HTTP Server and expose routes.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# ── Ensure Project Root is in sys.path BEFORE importing local packages ─────────
_BACKEND_DIR = Path(__file__).parent
_PROJECT_ROOT = _BACKEND_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Configure Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("backend.main")

# ── Local imports after path setup ─────────────────────────────────────────────
from backend.agents import anomaly_agent
from backend.rag import retriever
from backend.routers import predict, investigate, contain, timeline, cri, report


# ── Lifespan Startup & Teardown ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle app startup and shutdown tasks.

    Startup:
        1. Loads the Phase 1 Isolation Forest model bundle.
        2. Initialises the ChromaDB vector database index for Agent 2.

    If either asset is missing, startup will fail immediately with a descriptive
    error message and shutdown the process.
    """
    logger.info("Initializing SentinelX AI Lifespan startup sequence...")

    # ── Step 0: Initialize Database Tables ─────────────────────────────────────
    try:
        from backend.db.session import get_engine
        from backend.db.models import Base
        engine = get_engine()
        logger.info("Verifying and creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified.")
    except Exception as exc:
        logger.critical(f"Startup aborted: Failed to initialize database: {exc}", exc_info=True)
        sys.exit(1)

    # ── Step 1: Load Anomaly Model (Agent 1) ──────────────────────────────────
    try:
        anomaly_agent.load_model()
    except FileNotFoundError as exc:
        logger.critical(
            f"Startup aborted: Phase 1 model assets missing.\n"
            f"Error details: {exc}\n"
            "Action required: Run `python ml/train_model.py` first."
        )
        sys.exit(1)
    except Exception as exc:
        logger.critical(f"Startup aborted: Failed to load anomaly model: {exc}", exc_info=True)
        sys.exit(1)

    # ── Step 2: Load RAG Retriever Index (Agent 2) ────────────────────────────
    try:
        retriever.load_retriever()
    except FileNotFoundError as exc:
        logger.critical(
            f"Startup aborted: RAG Vector Database index is missing.\n"
            f"Error details: {exc}\n"
            "Action required: Build the index before starting the server using:\n\n"
            "    python backend/rag/build_index.py\n"
        )
        sys.exit(1)
    except Exception as exc:
        logger.critical(f"Startup aborted: Failed to load RAG retriever: {exc}", exc_info=True)
        sys.exit(1)

    logger.info("Lifespan startup sequence completed successfully. App is ready.")
    yield
    logger.info("Lifespan shutdown complete.")


# ── FastAPI App Instance ───────────────────────────────────────────────────────
app = FastAPI(
    title="SentinelX AI Backend",
    description=(
        "Advanced Behavioral Anomaly Detection & Incident Containment Engine. "
        "Consumes Phase 1 unsupervised Isolation Forest scores, maps features "
        "to MITRE ATT&CK via RAG reasoning, and automates asset containment rules."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route Registration ─────────────────────────────────────────────────────────
app.include_router(predict.router)
app.include_router(investigate.router)
app.include_router(contain.router)
app.include_router(timeline.router)
app.include_router(cri.router)
app.include_router(report.router)


# ── Global Health Check Endpoint ───────────────────────────────────────────────
@app.get("/health", tags=["System Diagnostics"])
def system_health() -> dict:
    """Return basic uptime health classification."""
    return {"status": "ok", "system": "SentinelX AI Backend"}


# ── Exception Handlers ─────────────────────────────────────────────────────────
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions to return standard RFC JSON errors."""
    logger.error(f"Unhandled exception encountered: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact administrator."}
    )
