"""
contain.py — SentinelX AI Phase 2 Router
==========================================
FastAPI router implementing:
    - POST /contain
    - POST /contain/approve

Integrates with risk_engine.py and commander_agent.py (Agent 3) to compute
risk, select containment actions, and log decisions to the audit trail.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import AuditLog, Event
from backend.agents import risk_engine, commander_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contain", tags=["Incident Response & Containment"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class ContainRequest(BaseModel):
    """Schema for containment evaluation requests."""
    record_id: str = Field(..., description="Unique flow identifier.")
    mitre_techniques: List[str] = Field(..., description="Identified MITRE technique IDs.")
    attack_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of threat presence.")
    asset_id: str = Field(..., description="Target system identifier.")


class ContainResponse(BaseModel):
    """Schema for containment response."""
    record_id: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_tier: str
    recommended_actions: List[str]
    approval_required: bool
    approval_state: str = Field(..., description="State: 'pending' or 'auto'")
    audit_log_id: str


class ApproveRequest(BaseModel):
    """Schema for action approval requests."""
    audit_log_id: str = Field(..., description="UUID of the audit log entry.")
    approved: bool = Field(..., description="Set True to execute recommended actions, False to reject.")
    approver: str = Field(..., description="Identifier of the operator/admin performing the approval.")


class ApproveResponse(BaseModel):
    """Schema for approval response."""
    audit_log_id: str
    status: str = Field(..., description="State: 'executed' or 'rejected'")
    executed_actions: List[str] = Field(..., description="Actions that were simulated as executed (empty if rejected).")


# ── POST /contain Endpoint ───────────────────────────────────────────────────
@router.post("", response_model=ContainResponse, status_code=status.HTTP_200_OK)
def contain_incident(request: ContainRequest, db: Session = Depends(get_db)) -> ContainResponse:
    """
    Evaluate incident risk and determine recommended containment actions.

    Steps:
        1. Calculate risk score and tier using the asset database.
        2. Assign mitigation actions and verify if human authorization is required.
        3. Write a record to the database audit_log table.
        4. Log a contain stage event to the events table.
        5. Return recommendations and the audit ID.
    """
    try:
        # Calculate risk score via Agent 3 (Risk Engine)
        risk_res = risk_engine.calculate_risk_score(request.attack_confidence, request.asset_id)
        risk_score = risk_res["risk_score"]
        risk_tier = risk_res["risk_tier"]

        # Determine actions via Agent 3 (Incident Commander)
        cmd_res = commander_agent.get_actions(risk_tier)
        recommended_actions = cmd_res["recommended_actions"]
        approval_required = cmd_res["approval_required"]
    except Exception as exc:
        logger.error(f"Unexpected risk scoring failure: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while evaluating incident containment risk."
        )

    # Initial state is 'pending' if manual review is needed, 'auto' if safe to proceed (monitor tier)
    approval_state = "pending" if approval_required else "auto"

    audit_id = uuid.uuid4()
    audit_id_str = str(audit_id)
    actions_joined = ",".join(recommended_actions)

    # ── Database Log (audit_log + events) ─────────────────────────────────────
    try:
        # Create audit trail row
        audit_entry = AuditLog(
            id=audit_id,
            record_id=request.record_id,
            action=actions_joined,
            risk_score=risk_score,
            risk_tier=risk_tier,
            approval_required=approval_required,
            approval_state=approval_state,
            approver=None,
            executed_at=None if approval_required else datetime.now(timezone.utc)
        )
        db.add(audit_entry)

        # Create history event entry
        event_entry = Event(
            record_id=request.record_id,
            stage="contain",
            payload={
                "request": request.model_dump(),
                "response": {
                    "risk_score": risk_score,
                    "risk_tier": risk_tier,
                    "recommended_actions": recommended_actions,
                    "approval_required": approval_required,
                    "approval_state": approval_state,
                    "audit_log_id": audit_id_str
                }
            }
        )
        db.add(event_entry)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database transaction failed for /contain {request.record_id!r}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist containment decisions to the database."
        )

    return ContainResponse(
        record_id=request.record_id,
        risk_score=risk_score,
        risk_tier=risk_tier,
        recommended_actions=recommended_actions,
        approval_required=approval_required,
        approval_state=approval_state,
        audit_log_id=audit_id_str
    )


# ── POST /contain/approve Endpoint ───────────────────────────────────────────
@router.post("/approve", response_model=ApproveResponse, status_code=status.HTTP_200_OK)
def approve_containment(request: ApproveRequest, db: Session = Depends(get_db)) -> ApproveResponse:
    """
    Approve or reject a pending containment recommendation.

    Modifies the state of an existing audit_log record:
        - If approved=True, changes approval_state to 'executed' and records the approver.
        - If approved=False, changes approval_state to 'rejected'.
        - Simulated execution only (real firewall/endpoint calls are commented).
    """
    try:
        audit_uuid = uuid.UUID(request.audit_log_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format for audit_log_id: '{request.audit_log_id}'"
        )

    # Fetch corresponding audit row
    entry = db.query(AuditLog).filter(AuditLog.id == audit_uuid).first()
    if not entry:
        logger.warning(f"Containment approval requested for non-existent audit ID: {request.audit_log_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log entry with ID '{request.audit_log_id}' not found."
        )

    # Check if transaction has already been processed
    if entry.approval_state in ("executed", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Containment request is already resolved (state={entry.approval_state!r})."
        )

    # Decode action strings from CSV
    actions = [act.strip() for act in entry.action.split(",") if act.strip()] if entry.action else []

    if request.approved:
        status_str = "executed"
        executed_actions = actions
        logger.info(
            f"[contain/approve] Executing actions {executed_actions} "
            f"for audit {request.audit_log_id} by {request.approver!r}"
        )
        # COMMENT: Real EDR/Firewall APIs would be called here. Execution is simulated.
    else:
        status_str = "rejected"
        executed_actions = []
        logger.info(
            f"[contain/approve] Containment rejected for audit "
            f"{request.audit_log_id} by {request.approver!r}"
        )

    # Update database record
    try:
        entry.approval_state = status_str
        entry.approver = request.approver
        entry.executed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to update audit log {request.audit_log_id} approval state: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update the approval status in the database."
        )

    return ApproveResponse(
        audit_log_id=request.audit_log_id,
        status=status_str,
        executed_actions=executed_actions
    )
