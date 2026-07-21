"""
timeline.py — SentinelX AI Phase 2 Router
===========================================
FastAPI router implementing the GET /timeline endpoint.

Queries the `events` and `audit_log` tables for entries recorded within a given
sliding historical window (e.g. 24h, 1h), merges them, and sorts by timestamp.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import AuditLog, Event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timeline", tags=["Dashboard & Telemetry"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class TimelineItem(BaseModel):
    """Schema for an individual entry in the combined historical timeline."""
    id: str = Field(..., description="Database UUID primary key.")
    record_id: str = Field(..., description="Flow record identifier.")
    source: str = Field(..., description="Source table: 'event' or 'audit_log'.")
    stage: str = Field(..., description="Intrusion stage or event type ('predict', 'investigate', 'contain', 'approve').")
    timestamp: str = Field(..., description="ISO8601 UTC timestamp of creation.")
    payload: Dict[str, Any] = Field(..., description="Full payload details or structured decision properties.")


class TimelineResponse(BaseModel):
    """Schema for the timeline response list."""
    items: List[TimelineItem] = Field(..., description="Chronologically sorted timeline items (oldest first).")
    count: int = Field(..., description="Total count of items in the window.")
    window: str = Field(..., description="The time window applied to query.")


# ── Time Window Parsing ────────────────────────────────────────────────────────
def parse_window_param(window_str: str) -> timedelta:
    """
    Parse a window string (e.g., '24h', '1h', '30m') into a Python timedelta.

    Supported units:
        d = days, h = hours, m = minutes

    Args:
        window_str: String representation of time length.

    Returns:
        Timedelta representing the time period.

    Raises:
        ValueError: If the format is invalid or unrecognised.
    """
    match = re.match(r"^(\d+)([dhm])$", window_str.strip().lower())
    if not match:
        raise ValueError(
            f"Invalid window format: '{window_str}'. "
            "Supported formats: integers followed by 'd', 'h', or 'm' (e.g. '24h', '7d', '45m')."
        )
    value = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return timedelta(days=value)
    elif unit == "h":
        return timedelta(hours=value)
    else:
        return timedelta(minutes=value)


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.get("", response_model=TimelineResponse, status_code=status.HTTP_200_OK)
def get_incident_timeline(
    window: str = Query("24h", description="Time window to retrieve (e.g. '24h', '12h', '1h')."),
    db: Session = Depends(get_db)
) -> TimelineResponse:
    """
    Retrieve a unified chronological timeline of all prediction and containment events.

    Queries:
        1. All records in `events` created within the window.
        2. All records in `audit_log` created within the window.

    Returns a chronologically merged list of events, formatted for easy frontend timeline rendering.
    """
    try:
        delta = parse_window_param(window)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    cutoff_time = datetime.now(timezone.utc) - delta

    items: List[TimelineItem] = []

    try:
        # ── 1. Fetch events ───────────────────────────────────────────────────
        events_list = db.query(Event).filter(Event.created_at >= cutoff_time).all()
        for ev in events_list:
            items.append(
                TimelineItem(
                    id=str(ev.id),
                    record_id=ev.record_id,
                    source="event",
                    stage=ev.stage,
                    timestamp=ev.created_at.isoformat(),
                    payload=ev.payload or {}
                )
            )

        # ── 2. Fetch audit logs ───────────────────────────────────────────────
        audits_list = db.query(AuditLog).filter(AuditLog.created_at >= cutoff_time).all()
        for aud in audits_list:
            # Map action list and approval properties to a structured payload dict
            payload = {
                "risk_score": aud.risk_score,
                "risk_tier": aud.risk_tier,
                "recommended_actions": [act.strip() for act in aud.action.split(",") if act.strip()] if aud.action else [],
                "approval_required": aud.approval_required,
                "approval_state": aud.approval_state,
                "approver": aud.approver,
                "executed_at": aud.executed_at.isoformat() if aud.executed_at else None
            }
            # For stage, distinguish between base contain and completed actions
            stage = "contain_approve" if aud.approval_state in ("executed", "rejected") else "contain"
            items.append(
                TimelineItem(
                    id=str(aud.id),
                    record_id=aud.record_id,
                    source="audit_log",
                    stage=stage,
                    timestamp=aud.created_at.isoformat(),
                    payload=payload
                )
            )
    except Exception as exc:
        logger.error(f"Database query failed during /timeline: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timeline records from the database."
        )

    # Sort merged list chronologically (oldest events first)
    items.sort(key=lambda x: x.timestamp)

    return TimelineResponse(
        items=items,
        count=len(items),
        window=window
    )
