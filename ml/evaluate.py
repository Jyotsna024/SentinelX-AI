"""
evaluate.py — SentinelX AI Phase 1
=====================================
Loads the held-out UNSW-NB15 testing set and the trained IsolationForest
bundle, computes all required metrics, prints a human-readable summary,
and saves metrics.json.

All metrics are computed from ACTUAL model predictions on ACTUAL test data.
No values are hardcoded or estimated.

Usage:
    python evaluate.py
"""

import sys
import json
import pathlib

import numpy as np
import joblib
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = pathlib.Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
MODEL_DIR   = BASE_DIR / "model"

MODEL_PATH  = MODEL_DIR / "isolation_forest.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
TEST_CACHE  = DATA_DIR  / "test_split_processed.joblib"
TEST_CSV    = DATA_DIR  / "UNSW_NB15_testing-set.csv"


# ──────────────────────────────────────────────────────────────────────────────
def load_artifacts() -> tuple:
    """Load the model bundle and preprocessed test data."""
    # ── Model bundle ───────────────────────────────────────────────────────────
    if not MODEL_PATH.exists():
        print(
            f"\n[ERROR] Model file not found: {MODEL_PATH}\n"
            "  Please run `python train_model.py` first.\n",
            file=sys.stderr,
        )
        sys.exit(1)
    bundle = joblib.load(MODEL_PATH)
    print(f"[LOAD] Model bundle loaded from {MODEL_PATH}")

    # ── Preprocessed test cache (fastest path) ─────────────────────────────────
    if TEST_CACHE.exists():
        cache = joblib.load(TEST_CACHE)
        X_test, y_test = cache["X_test"], cache["y_test"]
        print(f"[LOAD] Preprocessed test set loaded from cache ({len(y_test):,} records)")
    elif TEST_CSV.exists():
        # Fallback: re-preprocess from raw CSV
        print(f"[WARN] Cache not found — re-preprocessing {TEST_CSV} ...")
        import pandas as pd
        df_test     = pd.read_csv(TEST_CSV, low_memory=False)
        preprocessor = bundle["preprocessor"]
        num_cols    = bundle["num_cols"]
        cat_cols    = bundle["cat_cols"]
        X_test_raw  = df_test[num_cols + cat_cols]
        X_test      = preprocessor.transform(X_test_raw)
        y_test      = df_test["label"].values
        print(f"[LOAD] Re-preprocessed test set: {len(y_test):,} records")
    else:
        print(
            f"\n[ERROR] Neither the cached test set ({TEST_CACHE})\n"
            f"        nor the raw CSV ({TEST_CSV}) was found.\n"
            "  Please run `python train_model.py` first, or ensure\n"
            "  UNSW_NB15_testing-set.csv is in ml/data/.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    return bundle, X_test, y_test


# ──────────────────────────────────────────────────────────────────────────────
def compute_metrics(model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """
    Compute all required metrics.

    IsolationForest conventions:
      predict()           → +1 (normal / inlier) or -1 (anomaly / outlier)
      decision_function() → raw anomaly score (higher = MORE normal)

    We map predictions to binary labels matching the dataset convention:
      +1 (inlier)  → 0 (normal, not attack)
      -1 (outlier) → 1 (attack / anomaly)

    For ROC-AUC we use the decision_function score negated so that
    higher score = higher probability of being an attack.
    """
    # Raw predictions: +1 = normal, -1 = anomaly
    raw_preds = model.predict(X_test)

    # Convert to binary: 0 = normal, 1 = anomaly/attack
    y_pred = np.where(raw_preds == -1, 1, 0)

    # Anomaly score: higher = more anomalous (negate decision_function)
    anomaly_scores = -model.decision_function(X_test)

    # ── Core metrics ──────────────────────────────────────────────────────────
    accuracy  = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall    = recall_score(y_test, y_pred, zero_division=0)
    f1        = f1_score(y_test, y_pred, zero_division=0)
    roc_auc   = roc_auc_score(y_test, anomaly_scores)

    # ── False Positive Rate from confusion matrix ──────────────────────────────
    # FPR = FP / (FP + TN)  — fraction of normal records mis-flagged as attacks
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "n_test_records":  int(len(y_test)),
        "n_normal":        int(np.sum(y_test == 0)),
        "n_attack":        int(np.sum(y_test == 1)),
        "accuracy":        round(float(accuracy),  4),
        "precision":       round(float(precision), 4),
        "recall":          round(float(recall),    4),
        "f1_score":        round(float(f1),        4),
        "roc_auc":         round(float(roc_auc),   4),
        "false_positive_rate": round(float(fpr),   4),
        "confusion_matrix": {
            "tn": int(tn), "fp": int(fp),
            "fn": int(fn), "tp": int(tp),
        },
        "note": (
            "Metrics computed from IsolationForest on UNSW-NB15 testing-set. "
            "Anomaly (+1 label) = predicted as attack. "
            "ROC-AUC uses negated decision_function as the anomaly score."
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SentinelX AI — Phase 1 Evaluation")
    print("=" * 60)

    # ── Load ───────────────────────────────────────────────────────────────────
    bundle, X_test, y_test = load_artifacts()
    model = bundle["model"]

    # ── Compute metrics ────────────────────────────────────────────────────────
    print(f"\n[EVAL] Scoring {len(y_test):,} test records...")
    metrics = compute_metrics(model, X_test, y_test)

    # ── Save metrics.json ──────────────────────────────────────────────────────
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[SAVE] Metrics saved → {METRICS_PATH}")

    # ── Human-readable summary (slide-ready) ───────────────────────────────────
    cm = metrics["confusion_matrix"]
    print("\n" + "=" * 60)
    print("  Evaluation Results — UNSW-NB15 Test Set")
    print("=" * 60)
    print(f"  Records evaluated:  {metrics['n_test_records']:,}")
    print(f"  Normal traffic:     {metrics['n_normal']:,}")
    print(f"  Attack traffic:     {metrics['n_attack']:,}")
    print()
    print(f"  Accuracy:           {metrics['accuracy']:.4f}")
    print(f"  Precision:          {metrics['precision']:.4f}")
    print(f"  Recall:             {metrics['recall']:.4f}")
    print(f"  F1-Score:           {metrics['f1_score']:.4f}")
    print(f"  ROC-AUC:            {metrics['roc_auc']:.4f}")
    print(f"  False Positive Rate:{metrics['false_positive_rate']:.4f}")
    print()
    print(f"  Confusion Matrix:")
    print(f"    TN={cm['tn']:,}  FP={cm['fp']:,}")
    print(f"    FN={cm['fn']:,}  TP={cm['tp']:,}")
    print("=" * 60)

    # One-liner for copy-paste into a slide
    print(
        f"\n  ── Slide summary ──────────────────────────────────────\n"
        f"  Precision: {metrics['precision']:.2f}, "
        f"Recall: {metrics['recall']:.2f}, "
        f"F1: {metrics['f1_score']:.2f}, "
        f"ROC-AUC: {metrics['roc_auc']:.2f}, "
        f"FPR: {metrics['false_positive_rate']:.2f} "
        f"on {metrics['n_test_records']:,} test records"
        f"\n  ────────────────────────────────────────────────────────\n"
    )


if __name__ == "__main__":
    main()
