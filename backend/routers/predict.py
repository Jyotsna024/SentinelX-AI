"""
predict.py — SentinelX AI Phase 2 Router
==========================================
FastAPI router implementing the POST /predict endpoint.

Integrates with anomaly_agent.py (Agent 1) to run the unsupervised
Isolation Forest anomaly detection pipeline. Logs the event to the events table.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import Event
from backend.agents import anomaly_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Anomaly Detection"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    """Schema for prediction requests containing raw flow features."""
    record_id: str = Field(..., description="Unique identifier for the network flow record.")
    features: Dict[str, Any] = Field(..., description="Key-value mapping of raw UNSW-NB15 features.")


class PredictResponse(BaseModel):
    """Schema for the prediction response."""
    record_id: str
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score between 0 and 1.")
    is_anomalous: bool
    reason_codes: List[str]
    timestamp: str = Field(..., description="ISO8601 UTC timestamp of prediction.")


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("", response_model=PredictResponse, status_code=status.HTTP_200_OK)
def predict_flow(request: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    """
    Run behavioral anomaly detection on the supplied network flow record.

    Steps:
        1. Extract the raw features from the request.
        2. Delegate feature processing, scoring, and reason-code extraction to Agent 1.
        3. Persist the request and response payload to the PostgreSQL `events` table (stage='predict').
        4. Return the classification and scores.
    """
    try:
        # Run prediction through Agent 1
        res = anomaly_agent.predict(request.record_id, request.features)
    except ValueError as exc:
        # Features were missing or invalid (e.g. schema verification failed)
        logger.warning(f"Validation failed for /predict request {request.record_id!r}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_420_METHOD_FAILURE if hasattr(status, "HTTP_420_METHOD_FAILURE") else 422,
            detail=str(exc)
        )
    except RuntimeError as exc:
        # Model is not loaded
        logger.error(f"Internal model error during /predict: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly model is not loaded or initialization failed. Please check backend logs."
        )
    except Exception as exc:
        logger.error(f"Unexpected error in /predict: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction scoring."
        )

    timestamp_str = datetime.now(timezone.utc).isoformat()

    response_data = PredictResponse(
        record_id=request.record_id,
        anomaly_score=res["anomaly_score"],
        is_anomalous=res["is_anomalous"],
        reason_codes=res["reason_codes"],
        timestamp=timestamp_str
    )

    # ── Database Log (stage='predict') ────────────────────────────────────────
    try:
        event = Event(
            record_id=request.record_id,
            stage="predict",
            payload={
                "request": {
                    "record_id": request.record_id,
                    "features": request.features
                },
                "response": {
                    "anomaly_score": res["anomaly_score"],
                    "is_anomalous": res["is_anomalous"],
                    "reason_codes": res["reason_codes"],
                    "timestamp": timestamp_str
                }
            }
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        # Log database error, but do not fail the request (resilient design)
        db.rollback()
        logger.error(f"Failed to write prediction event to database: {exc}", exc_info=True)

    return response_data
