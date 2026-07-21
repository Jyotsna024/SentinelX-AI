"""
reason_codes.py — SentinelX AI Phase 1
========================================
Provides get_reason_codes(), which explains WHY a given record was flagged
as anomalous by the IsolationForest.

Method (z-score deviation heuristic):
  After preprocessing, each feature value is already expressed as a z-score
  relative to the training distribution (StandardScaler normalises numerics;
  OHE values of 0/1 are also measured against their training means).
  We rank features by |transformed_value - training_mean_of_that_feature|.
  The top-k most deviant features are returned as human-readable strings.

This is a transparent, defensible heuristic appropriate for a hackathon demo.
It is grounded in the actual values of the record being scored, not hardcoded.

No SHAP or tree-interpreter dependency required.
"""

from __future__ import annotations

import numpy as np


# Pre-compute training-set mean of each transformed feature once (lazily cached)
_TRAINING_MEANS_CACHE: dict[int, np.ndarray] = {}


def _get_transformed_feature_names(bundle: dict) -> list[str]:
    """Reconstruct the ordered list of feature names after OHE expansion."""
    preprocessor = bundle["preprocessor"]
    num_cols      = bundle["num_cols"]
    cat_cols      = bundle["cat_cols"]

    ohe = preprocessor.named_transformers_["cat"].named_steps["encoder"]
    ohe_names = []
    for col, categories in zip(cat_cols, ohe.categories_):
        ohe_names.extend([f"{col}={v}" for v in categories])

    return num_cols + ohe_names


def _compute_training_means(bundle: dict, X_normal: np.ndarray) -> np.ndarray:
    """
    Compute per-feature means from the NORMAL training distribution.
    After preprocessing, numeric features have mean ≈ 0 (StandardScaler),
    but we keep the general approach so it works even if the scaler drifts.
    """
    return X_normal.mean(axis=0)


def get_reason_codes(
    feature_vector: np.ndarray,
    bundle: dict,
    training_normal_X: np.ndarray | None = None,
    top_k: int = 5,
) -> list[str]:
    """
    Return a ranked list of human-readable reason codes explaining why
    `feature_vector` was scored as anomalous.

    Parameters
    ----------
    feature_vector : np.ndarray, shape (n_features,) or (1, n_features)
        A single preprocessed (transformed) feature vector, as returned
        by `preprocessor.transform(raw_df)`.
    bundle : dict
        The loaded model bundle from isolation_forest.joblib.
        Keys: 'preprocessor', 'model', 'num_cols', 'cat_cols'.
    training_normal_X : np.ndarray, optional
        Preprocessed normal-traffic training records.
        If provided, deviations are measured against the actual training
        mean/std.  If None, we rely on StandardScaler parameters
        (z-scores after scaling are centred at 0 for numeric features).
    top_k : int
        Number of top reason codes to return.

    Returns
    -------
    list[str]
        Up to `top_k` human-readable strings describing the most extreme
        feature deviations, e.g.:
          "dur: value=-0.12 (z=-0.12, 3.4σ from normal mean)"
    """
    vec = np.asarray(feature_vector).flatten()  # ensure 1-D

    feature_names = _get_transformed_feature_names(bundle)
    n_features    = len(feature_names)

    if len(vec) != n_features:
        raise ValueError(
            f"feature_vector has {len(vec)} elements but model expects {n_features}."
        )

    # ── Reference: mean of normal training distribution ────────────────────────
    if training_normal_X is not None:
        ref_mean = training_normal_X.mean(axis=0)
        ref_std  = training_normal_X.std(axis=0) + 1e-9
    else:
        # After StandardScaler, numeric features are already z-scores (mean≈0, std≈1)
        # OHE features: assume mean≈0 as a conservative approximation
        ref_mean = np.zeros(n_features)
        ref_std  = np.ones(n_features)

    # ── Compute absolute deviation from normal mean ────────────────────────────
    z_scores = np.abs((vec - ref_mean) / ref_std)

    # ── Rank by deviation, descending ─────────────────────────────────────────
    ranked_indices = np.argsort(z_scores)[::-1][:top_k]

    reasons = []
    for idx in ranked_indices:
        fname = feature_names[idx]
        raw   = vec[idx]
        z     = z_scores[idx]
        mean  = ref_mean[idx]

        direction = "above" if (vec[idx] - mean) > 0 else "below"
        reasons.append(
            f"{fname}: value={raw:.4f} ({z:.2f}σ {direction} normal mean of {mean:.4f})"
        )

    return reasons


def explain_record(
    raw_record: "pd.Series | dict",
    bundle: dict,
    training_normal_X: np.ndarray | None = None,
    top_k: int = 5,
) -> list[str]:
    """
    Convenience wrapper: accepts a raw (unprocessed) record as a dict or
    pd.Series, preprocesses it, and returns reason codes.

    Parameters
    ----------
    raw_record : dict or pd.Series
        Raw network-flow record with the same columns as the training CSV
        (excluding 'label' and 'attack_cat').
    bundle : dict
        Loaded model bundle.
    training_normal_X : np.ndarray, optional
        Preprocessed normal-traffic matrix (for reference distribution).
    top_k : int
        Number of reason codes to return.
    """
    import pandas as pd

    preprocessor = bundle["preprocessor"]
    num_cols     = bundle["num_cols"]
    cat_cols     = bundle["cat_cols"]
    all_cols     = num_cols + cat_cols

    # Build a single-row DataFrame
    if isinstance(raw_record, dict):
        df_row = pd.DataFrame([raw_record])[all_cols]
    else:
        df_row = pd.DataFrame([raw_record.to_dict()])[all_cols]

    vec = preprocessor.transform(df_row)[0]
    return get_reason_codes(vec, bundle, training_normal_X, top_k)
