"""
run_demo_attack.py — SentinelX AI Phase 4
=========================================
Demos the complete SentinelX AI intrusion detection and containment pipeline
by streaming curated records from the UNSW-NB15 test set over HTTP.

Usage:
    python simulation/run_demo_attack.py --speed normal --seed 42
"""

import argparse
import time
import sys
import pandas as pd
import requests
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

BASE_URL = "http://127.0.0.1:8000"

# Target asset mapping per attack stage
ATTACK_SEQUENCE = [
    {
        "stage_name": "Initial Access",
        "attack_cat": "Reconnaissance",
        "asset_id": "web_server",
        "narration": "Reconnaissance detected scanning public services. Target: Web Server."
    },
    {
        "stage_name": "Execution",
        "attack_cat": "Backdoor",
        "asset_id": "vpn_gateway",
        "narration": "Backdoor execution flagged on external border gateway. Target: VPN Gateway."
    },
    {
        "stage_name": "Credential Access",
        "attack_cat": "Analysis",
        "asset_id": "employee_laptop",
        "narration": "Credential harvesting and directory analysis behavior identified. Target: Employee Laptop."
    },
    {
        "stage_name": "Impact",
        "attack_cat": "Generic",
        "asset_id": "hospital_db",
        "narration": "Data encryption and lateral movement targeting primary patient records. Target: Hospital Database (CRITICAL ASSET)!",
        "force_critical": True # Override anomaly score to force critical risk tier
    }
]

def load_curated_records(seed: int):
    """
    Load 3 normal records and 4 escalating attack records deterministically from UNSW-NB15 test set.
    """
    test_csv = _ROOT / "ml" / "data" / "UNSW_NB15_testing-set.csv"
    if not test_csv.exists():
        print(f"[ERROR] Test dataset not found at {test_csv}", file=sys.stderr)
        print("Please download/train the model first by running ml/download_data.py and ml/train_model.py", file=sys.stderr)
        sys.exit(1)
        
    df = pd.read_csv(test_csv)
    
    # ── Load 3 normal records deterministically using seed ───────────────────
    normals = df[df["attack_cat"] == "Normal"].sample(n=3, random_state=seed)
    records = []
    
    for idx, row in normals.iterrows():
        records.append({
            "type": "normal",
            "stage_name": "Baseline Traffic",
            "asset_id": "file_server",
            "features": row.to_dict(),
            "narration": "Normal network transaction passing through. Target: File Server."
        })
        
    # ── Load 4 escalating attack records ──────────────────────────────────────
    for step in ATTACK_SEQUENCE:
        candidates = df[df["attack_cat"] == step["attack_cat"]]
        if candidates.empty:
            print(f"[ERROR] No records found in test set for category {step['attack_cat']}", file=sys.stderr)
            sys.exit(1)
        
        # Pick the first matching record
        row = candidates.iloc[0]
        records.append({
            "type": "attack",
            "stage_name": step["stage_name"],
            "asset_id": step["asset_id"],
            "features": row.to_dict(),
            "narration": step["narration"],
            "force_critical": step.get("force_critical", False)
        })
        
    return records

def run_simulation(speed: str, seed: int):
    delay = 1.0 if speed == "fast" else 3.0
    
    print("=" * 70)
    print("  SentinelX AI — Active Intrusion Simulator & Demo Runner")
    print(f"  Speed: {speed.upper()} ({delay}s delay) | Seed: {seed}")
    print("=" * 70)
    
    records = load_curated_records(seed)
    
    # Verify backend is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=3)
    except Exception:
        print("[ERROR] FastAPI backend is not running on http://127.0.0.1:8000. Start it first with uvicorn.", file=sys.stderr)
        sys.exit(1)

    for i, item in enumerate(records, 1):
        print(f"\n[{i}/7] {item['stage_name'].upper()}")
        print(f"NARRATION: {item['narration']}")
        
        # Prepare feature vector (strip non-feature columns)
        raw_features = item["features"]
        feature_payload = {}
        for k, v in raw_features.items():
            if k not in ("label", "attack_cat", "Unnamed: 0"):
                # Handle numeric vs string
                if isinstance(v, (int, float)) and pd.isna(v):
                    feature_payload[k] = 0.0
                elif isinstance(v, (int, float)):
                    feature_payload[k] = v
                else:
                    feature_payload[k] = str(v)
                    
        record_id = f"flow_sim_{int(time.time())}_{i}"
        
        # 1. Call POST /predict (Agent 1)
        print("  --> Calling POST /predict ...")
        pred_res = requests.post(
            f"{BASE_URL}/predict",
            json={"record_id": record_id, "features": feature_payload}
        ).json()
        
        anomaly_score = pred_res["anomaly_score"]
        is_anomalous = pred_res["is_anomalous"]
        reason_codes = pred_res["reason_codes"]
        
        print(f"  [predict] Score: {anomaly_score:.4f} | Anomalous: {is_anomalous}")
        
        if is_anomalous or item["type"] == "attack":
            time.sleep(delay / 2)
            
            # If we need to force a critical score for the final impact stage
            if item.get("force_critical"):
                anomaly_score = 0.98
                print("  [demo] Elevating anomaly score to 0.98 to simulate critical threat impact.")
            
            # 2. Call POST /investigate (Agent 2)
            print("  --> Calling POST /investigate ...")
            inv_res = requests.post(
                f"{BASE_URL}/investigate",
                json={
                    "record_id": record_id,
                    "anomaly_score": anomaly_score,
                    "reason_codes": reason_codes
                }
            ).json()
            
            mitre_techniques = inv_res["mitre_techniques"]
            attack_confidence = inv_res["attack_confidence"]
            
            tech_ids = [t["id"] for t in mitre_techniques]
            print(f"  [investigate] Techniques: {tech_ids} | Attack Confidence: {attack_confidence:.2f}")
            
            time.sleep(delay / 2)
            
            # 3. Call POST /contain (Agent 3)
            print("  --> Calling POST /contain ...")
            contain_payload = {
                "record_id": record_id,
                "mitre_techniques": tech_ids,
                "attack_confidence": attack_confidence,
                "asset_id": item["asset_id"]
            }
            cont_res = requests.post(
                f"{BASE_URL}/contain",
                json=contain_payload
            ).json()
            
            print(f"  [contain] Risk Score: {cont_res['risk_score']}/100 | Tier: {cont_res['risk_tier'].upper()}")
            print(f"  [contain] Actions: {cont_res['recommended_actions']}")
            print(f"  [contain] Approval Required: {cont_res['approval_required']} (State: {cont_res['approval_state']})")
            if cont_res['approval_required']:
                print(f"  [INCIDENT COMMANDER] Gate Pending! Log ID: {cont_res['audit_log_id']}")
                
        print(f"Waiting {delay} seconds...")
        time.sleep(delay)
        
    print("\n" + "=" * 70)
    print("  Simulation sequence complete. Navigate to the frontend to review logs.")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SentinelX demo simulator")
    parser.add_argument("--speed", choices=["fast", "normal"], default="normal", help="Simulation delay speed")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling normal records")
    args = parser.parse_args()
    
    run_simulation(args.speed, args.seed)
