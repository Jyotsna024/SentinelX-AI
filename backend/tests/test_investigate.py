"""
test_investigate.py — SentinelX AI Phase 2 Tests
==================================================
Unit tests for the POST /investigate endpoint.

Mocks the ChromaDB retriever and the Anthropic Claude API client to test threat
reasoning logic in isolation without making external network calls.
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.agents import mitre_agent


# ── Mocking Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_retriever_and_llm(monkeypatch):
    """
    Mock the LangChain VectorStore retriever and the Anthropic client.
    """
    # ── 1. Mock retriever ─────────────────────────────────────────────────────
    mock_retriever = MagicMock()
    # Mock document structure returned by retriever
    mock_doc = MagicMock()
    mock_doc.page_content = (
        "MITRE ATT&CK T1003: OS Credential Dumping. "
        "Attackers dump LSASS memory to harvest passwords and credentials. "
        "MITRE ATT&CK T1059: Command and Scripting Interpreter. "
        "PowerShell or Bash script executions."
    )
    mock_retriever.invoke.return_value = [mock_doc]

    # Patch get_retriever function
    monkeypatch.setattr("backend.rag.retriever.get_retriever", lambda: mock_retriever)

    # ── 2. Mock Anthropic Client ──────────────────────────────────────────────
    mock_client = MagicMock()

    # The mock response returned by Claude containing expected JSON payload
    mock_response_json = {
        "mitre_techniques": [
            {"id": "T1003", "name": "OS Credential Dumping", "confidence": 0.95},
            {"id": "T1059", "name": "Command and Scripting Interpreter", "confidence": 0.88}
        ],
        "explanation": "Observed high feature deviations on sbytes and port 445 indicating credential harvesting via PowerShell script.",
        "predicted_next_stage": "Lateral Movement",
        "attack_confidence": 0.92
    }

    mock_msg = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps(mock_response_json)
    mock_msg.content = [mock_content]
    mock_client.messages.create.return_value = mock_msg

    # Patch the _get_client helper to return our mock client
    monkeypatch.setattr(mitre_agent, "_get_client", lambda: mock_client)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_investigate_successful(client: TestClient, mock_db: MagicMock):
    """
    Test a successful POST /investigate run.
    Verify that:
        - Mapped MITRE technique IDs (T1003, T1059) are present in the response.
        - Explanation and confidence metrics are accurately parsed.
        - Database Event logging is executed.
    """
    payload = {
        "record_id": "flow-threat-01",
        "anomaly_score": 0.85,
        "reason_codes": [
            "sbytes: value=4500.0 (3.4σ above normal mean)",
            "port=445: NTLM credential dump pattern observed"
        ]
    }

    response = client.post("/investigate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["record_id"] == "flow-threat-01"

    # Assert expected techniques are mapped
    techniques = [tech["id"] for tech in data["mitre_techniques"]]
    assert "T1003" in techniques
    assert "T1059" in techniques

    # Verify confidence values are correct
    assert data["attack_confidence"] == 0.92
    assert "PowerShell" in data["explanation"]
    assert data["predicted_next_stage"] == "Lateral Movement"

    # Verify DB logging occurred (stage='investigate')
    assert mock_db.add.called
    assert mock_db.commit.called
