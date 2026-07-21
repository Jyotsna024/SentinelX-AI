"""
models.py — SentinelX AI Phase 2
===================================
SQLAlchemy ORM models for the three Phase 2 tables:
    - events
    - audit_log
    - cri_snapshots

All UUID primary keys use uuid.uuid4 as their Python-side default.
JSONB columns are used for flexible payload storage on PostgreSQL.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Integer, Text, DateTime, JSON, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Event(Base):
    """
    One row per agent pipeline invocation.

    Stages: 'predict', 'investigate', 'contain'
    The payload JSONB column captures the full request + response snapshot
    to support the /timeline endpoint and future auditing.
    """

    __tablename__ = "events"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    record_id: str = Column(Text, nullable=False, index=True)
    stage: str = Column(Text, nullable=False, index=True)
    payload: dict = Column(JSON, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} record_id={self.record_id!r} stage={self.stage!r}>"


class AuditLog(Base):
    """
    One row per /contain request, updated by /contain/approve.

    approval_state lifecycle:
        'pending' → set by /contain when approval_required is True
        'auto'    → set by /contain when risk_tier is 'monitor'
        'executed' | 'rejected' → set by /contain/approve
    """

    __tablename__ = "audit_log"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    record_id: str = Column(Text, nullable=False, index=True)
    action: str = Column(Text, nullable=True)          # comma-joined action list
    risk_score: int = Column(Integer, nullable=True)
    risk_tier: str = Column(Text, nullable=True)       # 'critical'|'elevated'|'monitor'
    approval_required: bool = Column(Boolean, nullable=True)
    approval_state: str = Column(Text, nullable=True, index=True)
    approver: str = Column(Text, nullable=True)        # populated on /contain/approve
    executed_at: datetime = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} record_id={self.record_id!r} "
            f"risk_tier={self.risk_tier!r} approval_state={self.approval_state!r}>"
        )


class CRISnapshot(Base):
    """
    One row per GET /cri invocation.

    Used by the CRI router to compute score trend (improving/declining/stable)
    by comparing the current score against the previous snapshot.
    """

    __tablename__ = "cri_snapshots"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    score: int = Column(Integer, nullable=False)
    status: str = Column(Text, nullable=False)    # 'healthy'|'elevated'|'critical'
    factors: dict = Column(JSON, nullable=True)
    captured_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<CRISnapshot id={self.id} score={self.score} status={self.status!r}>"
