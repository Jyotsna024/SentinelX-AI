"""
anomaly_agent.py — SentinelX AI Phase 2 / Agent 1
====================================================
Loads the Phase 1 IsolationForest model bundle at startup and exposes a
single `predict()` function used by routers/predict.py.

Phase 1 contract consumed (read-only, never modified):
    ml/model/isolation_forest.joblib  → bundle dict
    ml/model/feature_schema.json      → feature contract
    ml/reason_codes.get_reason_codes  → reason-code helper

Anomaly score normalisation:
    IsolationForest.decision_function() returns values where more negative
    means more anomalous. We normalize to [0, 1] with:

        clipped = clip(raw, -0.5, 0.5)
        anomaly_score = 1.0 - (clipped + 0.5)

    This maps: -0.5 (most anomalous) → 1.0, +0.5 (most normal) → 0.0.
    Clipping to [-0.5, 0.5] bounds the range typical of a well-tuned
    IsolationForest trained on network traffic data.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Path resolution ────────────────────────────────────────────────────────────
# backend/agents/anomaly_agent.py → backend/agents/ → backend/ → SentinelX-AI/
_BACKEND_DIR = Path(__file__).parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_ML_MODEL_DIR = _PROJECT_ROOT / "ml" / "model"

_MODEL_PATH = _ML_MODEL_DIR / "isolation_forest.joblib"
_SCHEMA_PATH = _ML_MODEL_DIR / "feature_schema.json"

# Ensure ml/ package is importable (Phase 1 lives at project root)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Module-level singletons ────────────────────────────────────────────────────
_bundle: Optional[dict] = None
_schema: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
def load_model() -> None:
    """
    Load the Phase 1 model bundle and feature schema into module-level singletons.

    Must be called once at FastAPI startup (via lifespan handler in main.py).
    Subsequent calls are no-ops (idempotent).

    Raises:
        FileNotFoundError: If isolation_forest.joblib or feature_schema.json
            are absent, with a clear message telling the user to run
            `python ml/train_model.py` first.
    """
    global _bundle, _schema

    if _bundle is not None:
        logger.debug("load_model() called again — model already loaded, skipping.")
        return

    if not _MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found: {_MODEL_PATH}\n"
            "Run `python ml/train_model.py` from the SentinelX-AI/ directory first."
        )
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Feature schema not found: {_SCHEMA_PATH}\n"
            "Run `python ml/train_model.py` from the SentinelX-AI/ directory first."
        )

    logger.info(f"Loading model bundle from {_MODEL_PATH} ...")
    _bundle = joblib.load(_MODEL_PATH)

    logger.info(f"Loading feature schema from {_SCHEMA_PATH} ...")
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        _schema = json.load(fh)

    feature_count = _schema.get("feature_count", "unknown")
    logger.info(
        f"Model loaded: IsolationForest, {feature_count} post-OHE features. "
        f"Numeric cols: {len(_bundle['num_cols'])}, "
        f"Categorical cols: {len(_bundle['cat_cols'])}."
    )


def _require_bundle() -> dict:
    """
    Return the loaded model bundle, raising if load_model() has not been called.

    Returns:
        The Phase 1 bundle dict with keys: preprocessor, model, num_cols, cat_cols.

    Raises:
        RuntimeError: If the model has not been loaded yet.
    """
    if _bundle is None:
        raise RuntimeError(
            "Anomaly model is not loaded. "
            "load_model() must be called at application startup."
        )
    return _bundle


def normalize_anomaly_score(raw_score: float) -> float:
    """
    Map a raw IsolationForest decision_function score to the [0, 1] range.

    Normalisation approach:
        1. Clip the raw score to [-0.5, 0.5] to handle outlier scores gracefully.
        2. Invert and shift: anomaly_score = 1.0 - (clipped + 0.5)

    Resulting mapping:
        raw = -0.5  → anomaly_score = 1.0  (maximally anomalous)
        raw =  0.0  → anomaly_score = 0.5  (borderline)
        raw = +0.5  → anomaly_score = 0.0  (maximally normal)

    Args:
        raw_score: Raw output from model.decision_function() for one sample.

    Returns:
        Normalized anomaly score as a float in [0.0, 1.0], rounded to 4 dp.
    """
    clipped = float(np.clip(raw_score, -0.5, 0.5))
    return round(1.0 - (clipped + 0.5), 4)


def predict(record_id: str, features: dict) -> dict:
    """
    Run anomaly detection on a single raw UNSW-NB15 network-flow record.

    Steps:
        1. Validate that all required feature columns are present.
        2. Build a single-row DataFrame in the column order expected by the
           Phase 1 ColumnTransformer.
        3. Apply the Phase 1 preprocessor (imputation + scaling + OHE).
        4. Score with IsolationForest: decision_function → anomaly_score,
           predict → is_anomalous.
        5. Call Phase 1 get_reason_codes() for human-readable explanations.

    Args:
        record_id: Caller-supplied identifier for logging / DB linkage.
        features:  Dict mapping raw UNSW-NB15 feature names to values.
                   Must include all columns listed in feature_schema.json
                   (excluding 'label' and 'attack_cat').

    Returns:
        Dict with keys:
            anomaly_score (float 0-1), is_anomalous (bool),
            reason_codes (list[str])

    Raises:
        ValueError:  If required feature columns are missing from `features`.
        RuntimeError: If the model has not been loaded at startup.
    """
    # Lazy import — avoids loading Phase 1 at module import time during tests
    from ml.reason_codes import get_reason_codes  # Phase 1 — not reimplemented

    bundle = _require_bundle()
    preprocessor = bundle["preprocessor"]
    model = bundle["model"]
    num_cols: list[str] = bundle["num_cols"]
    cat_cols: list[str] = bundle["cat_cols"]
    all_cols = num_cols + cat_cols

    # ── Validate presence of all required feature columns ─────────────────────
    missing = [col for col in all_cols if col not in features]
    if missing:
        raise ValueError(
            f"Missing required feature columns for record '{record_id}': {missing}"
        )

    # ── Build single-row DataFrame in the exact column order ──────────────────
    df_row = pd.DataFrame([{col: features[col] for col in all_cols}])

    # ── Apply Phase 1 preprocessor (impute → scale / OHE) ────────────────────
    X = preprocessor.transform(df_row)

    # ── Score ──────────────────────────────────────────────────────────────────
    raw_score = float(model.decision_function(X)[0])
    prediction = int(model.predict(X)[0])        # +1 = normal, -1 = anomaly

    anomaly_score = normalize_anomaly_score(raw_score)
    is_anomalous = prediction == -1

    logger.info(
        f"[predict] record_id={record_id!r} "
        f"raw={raw_score:.4f} score={anomaly_score:.4f} "
        f"anomalous={is_anomalous}"
    )

    # ── Reason codes via Phase 1 helper (not reimplemented) ───────────────────
    reason_codes: list[str] = get_reason_codes(X[0], bundle)

    return {
        "anomaly_score": anomaly_score,
        "is_anomalous": is_anomalous,
        "reason_codes": reason_codes,
    }
