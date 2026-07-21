"""
reset_demo.py — SentinelX AI Phase 4
======================================
Clears the database tables (events, audit_log, cri_snapshots)
to ensure a clean, stable baseline state before running a demo.
"""

import sys
from pathlib import Path

# Add project root to sys.path to allow imports of local packages
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.db.session import get_engine
from backend.db.models import Base

def reset_db():
    print("=" * 60)
    print("  SentinelX AI — Demo Database Reset Utility")
    print("=" * 60)
    
    try:
        engine = get_engine()
        
        print("[RESET] Dropping all existing database tables...")
        Base.metadata.drop_all(bind=engine)
        
        print("[RESET] Recreating database tables...")
        Base.metadata.create_all(bind=engine)
        
        print("[SUCCESS] Database reset complete! Everything is in a clean baseline state.")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR] Database reset failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    reset_db()
