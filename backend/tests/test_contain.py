"""
test_contain.py — SentinelX AI Phase 2 Tests
==============================================
Unit tests for POST /contain and POST /contain/approve endpoints.

Uses the asset_criticality_lookup.json configuration and verifies risk engine
calculations, incident commander actions, and database state transitions.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.db.models import AuditLog


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_contain_critical_risk(client: TestClient, mock_db: MagicMock):
    """
    Assert that a high attack confidence against a critical asset yields:
        - risk_score > 90
        - risk_tier = 'critical'
        - approval_required = True
        - approval_state = 'pending'
        - All 5 containment actions recommended.
    """
    payload = {
        "record_id": "flow-crit-01",
        "mitre_techniques": ["T1486", "T1021"],
        "attack_confidence": 0.98,
        "asset_id": "hospital_db"  # Criticality: 10, Impact: 1.0
    }

    # Formula: round(0.98 * (10 / 10) * 1.0 * 100) = 98

    response = client.post("/contain", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["record_id"] == "flow-crit-01"
    assert data["risk_score"] == 98
    assert data["risk_tier"] == "critical"
    assert data["approval_required"] is True
    assert data["approval_state"] == "pending"

    # Critical tier recommendations should contain all 5 options
    expected_actions = ["block_ip", "disable_account", "isolate_endpoint", "snapshot_vm", "notify_soc"]
    assert data["recommended_actions"] == expected_actions

    # Verify audit ID exists
    assert "audit_log_id" in data

    # Verify DB logging occurred
    assert mock_db.add.called
    assert mock_db.commit.called


def test_contain_monitor_risk(client: TestClient, mock_db: MagicMock):
    """
    Assert that a low attack confidence against a low criticality asset yields:
        - risk_score < 40
        - risk_tier = 'monitor'
        - approval_required = False
        - approval_state = 'auto'
        - recommended_actions = [] (empty)
    """
    payload = {
        "record_id": "flow-low-01",
        "mitre_techniques": ["T1083"],
        "attack_confidence": 0.20,
        "asset_id": "employee_laptop"  # Criticality: 3, Impact: 0.35
    }

    # Formula: round(0.20 * (3 / 10) * 0.35 * 100) = round(2.1) = 2

    response = client.post("/contain", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["record_id"] == "flow-low-01"
    assert data["risk_score"] == 2
    assert data["risk_tier"] == "monitor"
    assert data["approval_required"] is False
    assert data["approval_state"] == "auto"
    assert data["recommended_actions"] == []

    # Verify DB logging occurred
    assert mock_db.add.called
    assert mock_db.commit.called


def test_contain_approve_action(client: TestClient, mock_db: MagicMock):
    """
    Test manual containment approval execution.
    Verify:
        - approval_state updates to 'executed' in database.
        - recommended actions are returned in executed_actions.
    """
    # ── 1. Mock AuditLog database query result ────────────────────────────────
    mock_audit_entry = MagicMock(spec=AuditLog)
    mock_audit_entry.id = "497a9f7e-52f1-4db8-831d-d249f69747a8"
    mock_audit_entry.record_id = "flow-crit-01"
    mock_audit_entry.action = "block_ip,disable_account,isolate_endpoint"
    mock_audit_entry.approval_state = "pending"

    # Make the query filter return our mock entry
    mock_db.query.return_value.filter.return_value.first.return_value = mock_audit_entry

    # ── 2. Run request ────────────────────────────────────────────────────────
    payload = {
        "audit_log_id": "497a9f7e-52f1-4db8-831d-d249f69747a8",
        "approved": True,
        "approver": "sec_operator_01"
    }

    response = client.post("/contain/approve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["audit_log_id"] == "497a9f7e-52f1-4db8-831d-d249f69747a8"
    assert data["status"] == "executed"
    assert data["executed_actions"] == ["block_ip", "disable_account", "isolate_endpoint"]

    # Verify ORM updates occurred
    assert mock_audit_entry.approval_state == "executed"
    assert mock_audit_entry.approver == "sec_operator_01"
    assert mock_db.commit.called


def test_contain_reject_action(client: TestClient, mock_db: MagicMock):
    """
    Test manual containment rejection execution.
    Verify:
        - approval_state updates to 'rejected' in database.
        - executed_actions is empty.
    """
    # ── 1. Mock AuditLog database query result ────────────────────────────────
    mock_audit_entry = MagicMock(spec=AuditLog)
    mock_audit_entry.id = "8b6f3cd9-22a3-49ee-9467-d860d5b78f44"
    mock_audit_entry.record_id = "flow-crit-01"
    mock_audit_entry.action = "block_ip,disable_account"
    mock_audit_entry.approval_state = "pending"

    mock_db.query.return_value.filter.return_value.first.return_value = mock_audit_entry

    # ── 2. Run request ────────────────────────────────────────────────────────
    payload = {
        "audit_log_id": "8b6f3cd9-22a3-49ee-9467-d860d5b78f44",
        "approved": False,
        "approver": "sec_operator_01"
    }

    response = client.post("/contain/approve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "rejected"
    assert data["executed_actions"] == []

    # Verify ORM updates occurred
    assert mock_audit_entry.approval_state == "rejected"
    assert mock_db.commit.called
