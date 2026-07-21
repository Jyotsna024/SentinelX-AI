"""
train_model.py — SentinelX AI Phase 1
======================================
Trains an Isolation Forest anomaly detector on the UNSW-NB15 dataset.

Model: scikit-learn IsolationForest (unsupervised anomaly detection)
       Fit ONLY on label==0 (normal traffic) so the model learns the
       normal-behaviour manifold; anomaly scores are then computed for
       all records (normal + attack) in evaluate.py.

Substitution flag: NOT SUBSTITUTED — IsolationForest is used as specified.
"""

import sys
import json
import os
import pathlib

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = pathlib.Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
MODEL_DIR  = BASE_DIR / "model"

TRAIN_CSV  = DATA_DIR / "UNSW_NB15_training-set.csv"
TEST_CSV   = DATA_DIR / "UNSW_NB15_testing-set.csv"

MODEL_PATH  = MODEL_DIR / "isolation_forest.joblib"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"
TEST_CACHE  = DATA_DIR  / "test_split_processed.joblib"  # preprocessed test cache

# ─── Columns that must NOT be fed into the model ──────────────────────────────
# attack_cat: category label – not a network feature
# label:      ground-truth – the model is unsupervised, it never sees this
DROP_COLS = {"attack_cat", "label"}

# ─── Categorical columns that get OneHotEncoded ───────────────────────────────
CAT_COLS = ["proto", "service", "state"]


# ──────────────────────────────────────────────────────────────────────────────
def load_and_validate(path: pathlib.Path, name: str) -> pd.DataFrame:
    """Load a CSV, printing a clear error if it is absent."""
    if not path.exists():
        print(
            f"\n[ERROR] Expected file not found: {path}\n"
            f"  '{name}' must be placed at:\n"
            f"    {path.resolve()}\n\n"
            "  This script expects two files in ml/data/:\n"
            "    • UNSW_NB15_training-set.csv\n"
            "    • UNSW_NB15_testing-set.csv\n\n"
            "  Download them from the official UNSW-NB15 repository:\n"
            "    https://research.unsw.edu.au/projects/unsw-nb15-dataset\n",
            file=sys.stderr,
        )
        sys.exit(1)
    df = pd.read_csv(path, low_memory=False)
    print(f"[LOAD] {name}: {len(df):,} rows × {df.shape[1]} columns")
    return df


def get_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (numeric_cols, categorical_cols) after dropping non-feature cols."""
    all_cols = [c for c in df.columns if c not in DROP_COLS]
    cat_cols  = [c for c in CAT_COLS if c in all_cols]
    num_cols  = [c for c in all_cols if c not in cat_cols]
    return num_cols, cat_cols


def build_preprocessor(num_cols: list[str], cat_cols: list[str]) -> ColumnTransformer:
    """Build a ColumnTransformer: impute+scale numerics, impute+OHE categoricals."""
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("scaler",  StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, num_cols),
            ("cat", categorical_pipeline, cat_cols),
        ],
        remainder="drop",
    )
    return preprocessor


def build_feature_schema(
    num_cols: list[str],
    cat_cols: list[str],
    preprocessor: ColumnTransformer,
    X_train_transformed: np.ndarray,
) -> dict:
    """
    Build the feature_schema.json contract.

    The schema fully describes how to construct a feature vector from raw
    UNSW-NB15 fields so that the backend /predict endpoint can preprocess
    incoming records identically without guessing.
    """
    # ── Numeric feature metadata (mean + scale from the fitted StandardScaler) ─
    num_pipeline   = preprocessor.named_transformers_["num"]
    scaler: StandardScaler = num_pipeline.named_steps["scaler"]
    num_means  = scaler.mean_.tolist()
    num_scales = scaler.scale_.tolist()

    numeric_features = [
        {
            "name":  col,
            "type":  "numeric",
            "scaler_mean":  num_means[i],
            "scaler_scale": num_scales[i],
            "description": "Imputed (mean) then StandardScaled",
        }
        for i, col in enumerate(num_cols)
    ]

    # ── Categorical feature metadata (OHE category lists) ─────────────────────
    ohe: OneHotEncoder = preprocessor.named_transformers_["cat"].named_steps["encoder"]
    categorical_features = []
    for col, categories in zip(cat_cols, ohe.categories_):
        categorical_features.append({
            "name":       col,
            "type":       "categorical",
            "encoding":   "one_hot",
            "categories": categories.tolist(),
            "description": (
                "Imputed (most_frequent) then OneHotEncoded. "
                "Unknown values at inference are all-zeros (handle_unknown='ignore')."
            ),
        })

    # ── Ordered list of output feature names after transformation ─────────────
    # Numeric features come first, then OHE-expanded categoricals
    ohe_names = []
    for col, categories in zip(cat_cols, ohe.categories_):
        ohe_names.extend([f"{col}__{v}" for v in categories])
    transformed_feature_names = num_cols + ohe_names

    schema = {
        "schema_version": "1.0",
        "description": (
            "Feature contract for SentinelX AI IsolationForest model. "
            "Use this file to reproduce the exact feature vector expected by the model."
        ),
        "preprocessing_order": [
            "1. Drop columns: attack_cat, label (and any other non-feature columns).",
            "2. For numeric_features: fill NaN with scaler_mean, then apply z-score: (x - scaler_mean) / scaler_scale.",
            "3. For categorical_features: fill NaN with most frequent value, then one-hot encode using the listed categories. Unknown values → all zeros.",
            "4. Concatenate: [scaled_numeric_values..., ohe_cat1_values..., ohe_cat2_values..., ...]",
            "5. The resulting vector must have exactly feature_count elements in the order given by transformed_feature_names.",
        ],
        "feature_count": len(transformed_feature_names),
        "transformed_feature_names": transformed_feature_names,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "drop_columns": sorted(DROP_COLS),
        "model": {
            "type": "IsolationForest",
            "library": "scikit-learn",
            "scoring": (
                "model.decision_function(X) → raw anomaly score (higher = more normal). "
                "model.predict(X) → +1 (normal) or -1 (anomaly)."
            ),
            "training_note": "Model was fit ONLY on label==0 (normal traffic) records.",
        },
    }
    return schema


# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SentinelX AI — Phase 1 Training")
    print("=" * 60)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load data ───────────────────────────────────────────────────────────
    df_train = load_and_validate(TRAIN_CSV, "Training Set")
    df_test  = load_and_validate(TEST_CSV,  "Testing Set")

    # ── 2. Class balance summary ───────────────────────────────────────────────
    if "label" in df_train.columns:
        counts = df_train["label"].value_counts().sort_index()
        total  = len(df_train)
        print(f"\n[INFO] Training set class balance:")
        for lbl, cnt in counts.items():
            tag = "normal" if lbl == 0 else "attack"
            print(f"       label={lbl} ({tag:>6}): {cnt:>7,}  ({cnt/total*100:.1f}%)")
    else:
        print("[WARN] 'label' column not found — skipping class balance summary.")

    # ── 3. Identify feature columns ────────────────────────────────────────────
    num_cols, cat_cols = get_feature_columns(df_train)
    print(f"\n[INFO] Feature columns selected:")
    print(f"       Numeric ({len(num_cols)}): {num_cols}")
    print(f"       Categorical ({len(cat_cols)}): {cat_cols}")

    # ── 4. Build preprocessing pipeline ───────────────────────────────────────
    preprocessor = build_preprocessor(num_cols, cat_cols)

    # ── 5. Fit preprocessor on ALL training data (normal + attack) ─────────────
    #       This ensures the scaler/OHE see the full value range, but we'll
    #       fit the IsolationForest only on normal records below.
    X_train_all = df_train[num_cols + cat_cols]
    print(f"\n[INFO] Fitting preprocessor on all {len(X_train_all):,} training records...")
    preprocessor.fit(X_train_all)

    # ── 6. Filter to NORMAL traffic only for IsolationForest training ──────────
    normal_mask  = df_train["label"] == 0
    df_normal    = df_train[normal_mask]
    X_normal_raw = df_normal[num_cols + cat_cols]
    X_normal     = preprocessor.transform(X_normal_raw)
    print(f"[INFO] IsolationForest will be fit on {len(X_normal):,} normal-traffic records.")

    # ── 7. Also transform the full training set (for schema validation) ────────
    X_train_transformed = preprocessor.transform(X_train_all)
    n_features = X_train_transformed.shape[1]

    # ── 8. Train IsolationForest ───────────────────────────────────────────────
    print(f"\n[TRAIN] Training IsolationForest on {len(X_normal):,} normal records "
          f"with {n_features} features...")
    iso_forest = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        contamination=0.05,   # expected fraction of anomalies at prediction time
        random_state=42,
        n_jobs=-1,
    )
    iso_forest.fit(X_normal)
    print("[TRAIN] Training complete.")

    # ── 9. Build combined pipeline object for joblib serialisation ─────────────
    #       We store preprocessor and model together in a dict so evaluate.py
    #       gets a single self-contained artifact.
    bundle = {
        "preprocessor": preprocessor,
        "model":        iso_forest,
        "num_cols":     num_cols,
        "cat_cols":     cat_cols,
    }

    # ── 10. Pre-process and cache the test set ─────────────────────────────────
    X_test_raw = df_test[num_cols + cat_cols]
    y_test     = df_test["label"].values
    X_test     = preprocessor.transform(X_test_raw)
    test_cache = {"X_test": X_test, "y_test": y_test}
    joblib.dump(test_cache, TEST_CACHE)
    print(f"[SAVE] Preprocessed test set cached → {TEST_CACHE}")

    # ── 11. Save model bundle ──────────────────────────────────────────────────
    joblib.dump(bundle, MODEL_PATH)
    print(f"[SAVE] Model bundle saved → {MODEL_PATH}")

    # ── 12. Build and save feature schema ─────────────────────────────────────
    schema = build_feature_schema(num_cols, cat_cols, preprocessor, X_train_transformed)
    with open(SCHEMA_PATH, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"[SAVE] Feature schema saved → {SCHEMA_PATH}")

    # ── 13. Final summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Training Summary")
    print("=" * 60)
    print(f"  Training records (all):    {len(df_train):>8,}")
    print(f"  Training records (normal): {len(df_normal):>8,}")
    print(f"  Test records:              {len(df_test):>8,}")
    print(f"  Feature count (post-OHE):  {n_features:>8,}")
    print(f"  IsolationForest estimators:{iso_forest.n_estimators:>8,}")
    print(f"  Contamination parameter:   {iso_forest.contamination:>8}")
    print("=" * 60)
    print("\nNext step: run `python evaluate.py` to compute metrics.\n")


if __name__ == "__main__":
    main()
