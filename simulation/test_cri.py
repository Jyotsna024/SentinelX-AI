import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone
import requests

# Point to backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DB URL
os.environ["DATABASE_URL"] = "sqlite:///sentinelx_test.db"

from backend.db.session import get_engine, get_session_factory
from backend.db.models import Base, AuditLog, Event

# Reset DB
engine = get_engine()
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

SessionLocal = get_session_factory()
db = SessionLocal()

# Add a pending audit log
audit_id = uuid.uuid4()
aud = AuditLog(
    id=audit_id,
    record_id="flow_1",
    action="block_ip",
    risk_score=90,
    risk_tier="critical",
    approval_required=True,
    approval_state="pending",
    created_at=datetime.now(timezone.utc)
)
db.add(aud)
db.commit()

# Call CRI logic directly (simulate GET /cri)
from backend.routers.cri import get_criticality_risk_index
res1 = get_criticality_risk_index(db)
print("Before approve, open incidents:", res1.factors.unresolved_incidents)

# Approve it
aud = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
aud.approval_state = "executed"
aud.executed_at = datetime.now(timezone.utc)
db.commit()

# Call CRI logic directly
res2 = get_criticality_risk_index(db)
print("After approve, open incidents:", res2.factors.unresolved_incidents)

db.close()
