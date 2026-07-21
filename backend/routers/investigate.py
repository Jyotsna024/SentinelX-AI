"""
investigate.py — SentinelX AI Phase 2 Router
===============================================
FastAPI router implementing the POST /investigate endpoint.

Integrates with mitre_agent.py (Agent 2) to perform RAG-augmented analysis.
Retrieves relevant MITRE ATT&CK/CVE techniques and generates an LLM-powered
explanation, then records the investigation to the events table.
"""

import logging
from typing import List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import Event
from backend.agents import mitre_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investigate", tags=["MITRE & RAG Reasoning"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class InvestigateRequest(BaseModel):
    """Schema for investigation requests."""
    record_id: str = Field(..., description="Unique flow identifier.")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized score from /predict.")
    reason_codes: List[str] = Field(..., description="Top feature deviations indicating the anomaly.")


class MitreTechnique(BaseModel):
    """Schema for individual MITRE ATT&CK technique details."""
    id: str = Field(..., description="MITRE Technique ID (e.g. T1059).")
    name: str = Field(..., description="Technique name.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM confidence in this mapping.")


class InvestigateResponse(BaseModel):
    """Schema for the investigation response."""
    record_id: str
    mitre_techniques: List[MitreTechnique] = Field(..., description="Mapped MITRE ATT&CK techniques.")
    explanation: str = Field(..., description="LLM-generated threat explanation.")
    predicted_next_stage: str = Field(..., description="Expected threat progression stage.")
    attack_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall likelihood of malicious activity.")


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("", response_model=InvestigateResponse, status_code=status.HTTP_200_OK)
def investigate_flow(request: InvestigateRequest, db: Session = Depends(get_db)) -> InvestigateResponse:
    """
    Investigate an anomaly using RAG and LLM reasoning.

    Steps:
        1. Queries the local vector database using reason codes.
        2. Retrieves background threat context for matching techniques.
        3. Calls the Anthropic Claude model to interpret features and predict attacks.
        4. Saves the investigation to the events table (stage='investigate').
        5. Returns the threat model.
    """
    try:
        # Perform RAG + LLM analysis via Agent 2
        res = mitre_agent.investigate(
            record_id=request.record_id,
            anomaly_score=request.anomaly_score,
            reason_codes=request.reason_codes
        )
    except EnvironmentError as exc:
        # Anthropic API Key is missing
        logger.error(f"Configuration error for /investigate: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The reasoning agent is currently unavailable (API key missing)."
        )
    except ValueError as exc:
        # JSON formatting error from LLM
        logger.error(f"Reasoning agent returned malformed output: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The reasoning agent returned an invalid response: {exc}"
        )
    except Exception as exc:
        logger.error(f"Unexpected error in /investigate: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the investigation report."
        )

    # Reconstruct techniques list to fit response schema
    techniques = [
        MitreTechnique(
            id=tech["id"],
            name=tech["name"],
            confidence=tech["confidence"]
        )
        for tech in res["mitre_techniques"]
    ]

    response_data = InvestigateResponse(
        record_id=request.record_id,
        mitre_techniques=techniques,
        explanation=res["explanation"],
        predicted_next_stage=res["predicted_next_stage"],
        attack_confidence=res["attack_confidence"]
    )

    # ── Database Log (stage='investigate') ─────────────────────────────────────
    try:
        event = Event(
            record_id=request.record_id,
            stage="investigate",
            payload={
                "request": request.model_dump(),
                "response": response_data.model_dump()
            }
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to write investigation event to database: {exc}", exc_info=True)

    return response_data
