"""
cri.py — SentinelX AI Phase 2 Router
======================================
FastAPI router implementing the GET /cri endpoint.

Calculates the Criticality Risk Index (CRI), saves a snapshot to database
for trend tracking, and returns the status, trend, and active risk factors.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import AuditLog, CRISnapshot, Event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cri", tags=["Security Operations & Health"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class CRIFactors(BaseModel):
    """Sub-schema for risk factors contributing to the CRI score."""
    active_anomalies: int = Field(..., description="Number of anomalies with score > 0.5 in the last hour.")
    unresolved_incidents: int = Field(..., description="Number of pending critical or elevated incidents in the last hour.")
    avg_risk_score: float = Field(..., description="Average risk score of incidents evaluated in the last hour.")


class CRIResponse(BaseModel):
    """Schema for the CRI response."""
    score: int = Field(..., ge=0, le=100, description="Computed health score where 100 is fully secure.")
    status: str = Field(..., description="Bands: >75 'healthy', 40-75 'elevated', <40 'critical'")
    trend: str = Field(..., description="State: 'improving', 'declining', or 'stable' compared to the last snapshot.")
    factors: CRIFactors = Field(..., description="Breakdown of factors contributing to the score calculation.")


# ── Health Band Mapping ────────────────────────────────────────────────────────
def _get_health_status(score: int) -> str:
    """Return health band tag based on integer score."""
    if score > 75:
        return "healthy"
    elif score >= 40:
        return "elevated"
    else:
        return "critical"


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.get("", response_model=CRIResponse, status_code=status.HTTP_200_OK)
def get_criticality_risk_index(db: Session = Depends(get_db)) -> CRIResponse:
    """
    Calculate and retrieve the live Criticality Risk Index (CRI).

    Algorithm:
        1. Fetch all audit logs and events from the last 1 hour.
        2. Score starts at 100.
        3. Deduct 15 points per pending critical incident.
        4. Deduct 8 points per pending elevated incident.
        5. Add 5 points per executed containment action.
        6. Clamp score between 0 and 100.
        7. Query the database for the last snapshot to determine trend.
        8. Write the new score snapshot to the `cri_snapshots` table.
        9. Return metrics.
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    try:
        # ── 1. Fetch relevant logs from the database ──────────────────────────
        audits = db.query(AuditLog).filter(AuditLog.created_at >= one_hour_ago).all()
        events = db.query(Event).filter(
            Event.stage == "predict",
            Event.created_at >= one_hour_ago
        ).all()
    except Exception as exc:
        logger.error(f"Database query failed during CRI compilation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health telemetry from the database."
        )

    # ── 2. Calculate CRI Score ────────────────────────────────────────────────
    score = 100
    pending_critical = 0
    pending_elevated = 0
    executed_count = 0
    total_risk_sum = 0.0
    audit_count = len(audits)

    for aud in audits:
        total_risk_sum += (aud.risk_score or 0)

        if aud.approval_state == "pending":
            if aud.risk_tier == "critical":
                pending_critical += 1
                score -= 15
            elif aud.risk_tier == "elevated":
                pending_elevated += 1
                score -= 8
        elif aud.approval_state == "executed":
            executed_count += 1
            score += 5

    # Clamp score to [0, 100]
    score = max(0, min(100, score))
    status_str = _get_health_status(score)

    # ── 3. Calculate Factors ──────────────────────────────────────────────────
    # Count predictions in the last hour where anomaly_score > 0.5
    active_anomalies = 0
    for ev in events:
        try:
            payload = ev.payload or {}
            resp = payload.get("response", {})
            anom_score = resp.get("anomaly_score", 0.0)
            if anom_score > 0.5:
                active_anomalies += 1
        except Exception:
            # Shield against missing keys or formatting variations in logs
            continue

    unresolved_incidents = pending_critical + pending_elevated
    avg_risk_score = (total_risk_sum / audit_count) if audit_count > 0 else 0.0

    factors = CRIFactors(
        active_anomalies=active_anomalies,
        unresolved_incidents=unresolved_incidents,
        avg_risk_score=round(avg_risk_score, 2)
    )

    # ── 4. Determine Trend (Compare against previous database snapshot) ───────
    trend = "stable"
    try:
        prev_snapshot = db.query(CRISnapshot).order_by(CRISnapshot.captured_at.desc()).first()
        if prev_snapshot:
            if score > prev_snapshot.score:
                trend = "improving"
            elif score < prev_snapshot.score:
                trend = "declining"
            else:
                trend = "stable"
    except Exception as exc:
        # DB failure here should not block response
        logger.warning(f"Failed to fetch previous CRI snapshot for trend tracking: {exc}")

    # ── 5. Save Snapshot to Database ──────────────────────────────────────────
    try:
        snapshot = CRISnapshot(
            score=score,
            status=status_str,
            factors=factors.model_dump()
        )
        db.add(snapshot)
        db.commit()
        logger.info(f"[CRI] Saved new index snapshot: score={score} status={status_str}")
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to save CRI snapshot to database: {exc}", exc_info=True)
        # We don't fail the HTTP request if snapshot writing fails, return telemetry anyway

    return CRIResponse(
        score=score,
        status=status_str,
        trend=trend,
        factors=factors
    )
