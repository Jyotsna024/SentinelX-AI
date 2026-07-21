import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, method, path, payload=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {name} ({method} {path}) ...")
    try:
        if method == "GET":
            res = requests.get(url, timeout=5)
        else:
            res = requests.post(url, json=payload, timeout=5)
        
        print(f"  Status Code: {res.status_code}")
        if res.status_code in (200, 201):
            data = res.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"  Error Response: {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  Failed: {e}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("  SentinelX AI End-to-End API Verification")
    print("=" * 60)

    # 1. Health & Docs
    try:
        res = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"Docs UI Health check: {res.status_code} OK")
    except Exception as e:
        print(f"Docs UI unreachable: {e}")
        sys.exit(1)

    # 2. Predict Anomaly (Agent 1)
    predict_payload = {
        "record_id": "record_demo_01",
        "features": {
            "id": 1,
            "dur": 0.05,
            "proto": "tcp",
            "service": "http",
            "state": "FIN",
            "spkts": 12,
            "dpkts": 10,
            "sbytes": 850,
            "dbytes": 1400,
            "rate": 120.5,
            "sttl": 31,
            "dttl": 29,
            "sload": 15000.0,
            "dload": 12000.0,
            "sloss": 2,
            "dloss": 2,
            "sinpkt": 0.01,
            "dinpkt": 0.01,
            "sjit": 10.0,
            "djit": 10.0,
            "swin": 255,
            "stcpb": 1234567,
            "dtcpb": 7654321,
            "dwin": 255,
            "tcprtt": 0.002,
            "synack": 0.001,
            "ackdat": 0.001,
            "smean": 70,
            "dmean": 140,
            "trans_depth": 0,
            "response_body_len": 0,
            "ct_srv_src": 2,
            "ct_state_ttl": 0,
            "ct_dst_ltm": 1,
            "ct_src_dport_ltm": 1,
            "ct_dst_sport_ltm": 1,
            "ct_dst_src_ltm": 1,
            "is_ftp_login": 0,
            "ct_ftp_cmd": 0,
            "ct_flw_http_mthd": 0,
            "ct_src_ltm": 1,
            "ct_srv_dst": 1,
            "is_sm_ips_ports": 0
        }
    }
    pred = test_endpoint("Agent 1 - Predict", "POST", "/predict", predict_payload)

    # 3. Investigate Threat (Agent 2)
    inv_payload = {
        "record_id": pred["record_id"],
        "anomaly_score": pred["anomaly_score"],
        "reason_codes": pred["reason_codes"]
    }
    inv = test_endpoint("Agent 2 - Investigate", "POST", "/investigate", inv_payload)

    # 4. Contain Risk (Agent 3)
    tech_ids = [t["id"] for t in inv["mitre_techniques"]]
    contain_payload = {
        "record_id": pred["record_id"],
        "mitre_techniques": tech_ids,
        "attack_confidence": inv["attack_confidence"],
        "asset_id": "employee_laptop"
    }
    cont = test_endpoint("Agent 3 - Contain", "POST", "/contain", contain_payload)

    # 5. Contain Approve (Incident Commander)
    if cont.get("approval_required") and cont.get("audit_log_id"):
        app_payload = {
            "audit_log_id": cont["audit_log_id"],
            "approved": True,
            "approver": "sec_operator_01"
        }
        test_endpoint("Incident Commander - Approve", "POST", "/contain/approve", app_payload)

    # 6. Telemetry - CRI
    test_endpoint("Telemetry - CRI", "GET", "/cri")

    # 7. Telemetry - Timeline
    test_endpoint("Telemetry - Timeline", "GET", "/timeline?window=24h")

    print("\n" + "=" * 60)
    print("  All backend API endpoints verified successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
