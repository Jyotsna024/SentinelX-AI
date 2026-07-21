"""
test_predict.py — SentinelX AI Phase 2 Tests
==============================================
Unit tests for the POST /predict endpoint.

Mocks the Phase 1 IsolationForest model and preprocessor so that tests
run reliably in an isolated pipeline without requiring pre-trained files
or a database.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Mock Preprocessor and Model for IsolationForest ──────────────────────────
class MockEncoder:
    """Mock OneHotEncoder for reason code extraction."""
    def __init__(self):
        self.categories_ = [
            np.array(["tcp", "udp"]),
            np.array(["http", "dns", "smtp"]),
            np.array(["FIN", "INT", "CON"])
        ]


class MockCatPipeline:
    """Mock pipeline holding the encoder step."""
    def __init__(self):
        self.named_steps = {"encoder": MockEncoder()}


class MockPreprocessor:
    """Mock ColumnTransformer to transform test dataframes into arrays."""
    def __init__(self):
        self.named_transformers_ = {"cat": MockCatPipeline()}

    def transform(self, df):
        # We construct a 10-dimensional feature vector.
        # Element 0 represents 'dur'.
        dur_val = float(df["dur"].iloc[0])
        arr = np.zeros((1, 10))
        arr[0, 0] = dur_val
        return arr


class MockModel:
    """Mock IsolationForest model."""
    def decision_function(self, X):
        # If 'dur' (element 0) is extremely high, score is anomalous (< 0)
        if X[0, 0] > 100.0:
            return np.array([-0.4])
        return np.array([0.4])

    def predict(self, X):
        # -1 represents anomaly, +1 represents normal
        if X[0, 0] > 100.0:
            return np.array([-1])
        return np.array([1])


@pytest.fixture(autouse=True)
def setup_mock_agent(monkeypatch):
    """
    Automatically inject mock model bundle and schema into anomaly_agent
    before running any test.
    """
    from backend.agents import anomaly_agent

    # Create a mock bundle using our mocks
    mock_bundle = {
        "preprocessor": MockPreprocessor(),
        "model": MockModel(),
        "num_cols": ["dur", "sbytes", "dbytes", "spkts", "dpkts"],
        "cat_cols": ["proto", "service", "state"]
    }

    mock_schema = {
        "feature_count": 10,
        "transformed_feature_names": [
            "dur", "sbytes", "dbytes", "spkts", "dpkts",
            "proto__tcp", "proto__udp",
            "service__http", "service__dns", "service__smtp"
        ]
    }

    # Override the module-level singletons in anomaly_agent
    monkeypatch.setattr(anomaly_agent, "_bundle", mock_bundle)
    monkeypatch.setattr(anomaly_agent, "_schema", mock_schema)
    # Make load_model a no-op
    monkeypatch.setattr(anomaly_agent, "load_model", lambda: None)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_predict_normal_flow(client: TestClient, mock_db: MagicMock):
    """
    Assert that a known-normal-looking flow returns:
        - anomaly_score near 0.0 (low anomaly likelihood)
        - is_anomalous = False
    """
    # Define normal feature mapping matching the schema
    features = {
        "dur": 0.12,
        "sbytes": 500,
        "dbytes": 1000,
        "spkts": 10,
        "dpkts": 20,
        "proto": "tcp",
        "service": "http",
        "state": "FIN"
    }

    payload = {
        "record_id": "flow-normal-01",
        "features": features
    }

    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["record_id"] == "flow-normal-01"
    assert data["is_anomalous"] is False
    # Normal raw decision_function = 0.4.
    # Normalisation: 1.0 - (0.4 + 0.5) = 0.1
    assert abs(data["anomaly_score"] - 0.1) < 1e-4
    assert len(data["reason_codes"]) > 0
    assert "timestamp" in data

    # Verify database write occurred
    assert mock_db.add.called
    assert mock_db.commit.called


def test_predict_anomalous_flow(client: TestClient, mock_db: MagicMock):
    """
    Assert that an extreme outlier flow returns:
        - anomaly_score near 1.0 (high anomaly likelihood)
        - is_anomalous = True
    """
    # Define an outlier feature mapping ('dur' is exceptionally high)
    features = {
        "dur": 999.9,
        "sbytes": 500,
        "dbytes": 1000,
        "spkts": 10,
        "dpkts": 20,
        "proto": "tcp",
        "service": "http",
        "state": "FIN"
    }

    payload = {
        "record_id": "flow-anom-99",
        "features": features
    }

    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["record_id"] == "flow-anom-99"
    assert data["is_anomalous"] is True
    # Outlier raw decision_function = -0.4.
    # Normalisation: 1.0 - (-0.4 + 0.5) = 0.9
    assert abs(data["anomaly_score"] - 0.9) < 1e-4
    assert len(data["reason_codes"]) > 0
    assert "timestamp" in data

    # Verify database write occurred
    assert mock_db.add.called
    assert mock_db.commit.called


def test_predict_missing_features(client: TestClient):
    """
    Assert that a request missing required schema features returns HTTP 422
    or HTTP 420.
    """
    payload = {
        "record_id": "flow-invalid-01",
        "features": {
            "dur": 0.12  # missing other features
        }
    }

    response = client.post("/predict", json=payload)
    assert response.status_code in (422, 420)
