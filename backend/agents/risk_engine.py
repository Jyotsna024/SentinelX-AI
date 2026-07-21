"""
risk_engine.py — SentinelX AI Phase 2 / Agent 3 (Risk)
=========================================================
Calculates a normalized risk score (0-100) for a given asset and attack
confidence value, and assigns it a risk tier.

Formula (exactly as specified):
    risk_score = round(attack_confidence × (criticality / 10) × impact_weight × 100)

Tiers:
    > 90       → "critical"
    40 to 90   → "elevated"
    < 40       → "monitor"

Asset data is loaded from agents/asset_criticality_lookup.json.
Unknown assets fall back to criticality=5, impact_weight=0.5 with a warning.
"""

import json
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

_LOOKUP_PATH = Path(__file__).parent / "asset_criticality_lookup.json"

# ── Tier type alias ────────────────────────────────────────────────────────────
RiskTier = Literal["critical", "elevated", "monitor"]

# ── Default for unknown assets ─────────────────────────────────────────────────
_UNKNOWN_ASSET_DEFAULT = {"criticality": 5, "impact_weight": 0.5}

# ── Module-level singleton ─────────────────────────────────────────────────────
_asset_lookup: dict | None = None


def _load_asset_lookup() -> dict:
    """
    Load and cache the asset criticality lookup JSON.

    Returns:
        Dict mapping asset_id → {"criticality": int, "impact_weight": float}.

    Raises:
        FileNotFoundError: If asset_criticality_lookup.json is missing.
    """
    global _asset_lookup
    if _asset_lookup is None:
        if not _LOOKUP_PATH.exists():
            raise FileNotFoundError(
                f"Asset criticality lookup not found: {_LOOKUP_PATH}"
            )
        with open(_LOOKUP_PATH, encoding="utf-8") as fh:
            _asset_lookup = json.load(fh)
        logger.info(f"Asset lookup loaded: {len(_asset_lookup)} entries.")
    return _asset_lookup


def _assign_tier(risk_score: int) -> RiskTier:
    """
    Assign a risk tier based on the integer risk score.

    Tier thresholds (exclusive upper bound at 90):
        > 90  → "critical"
        40-90 → "elevated"
        < 40  → "monitor"

    Args:
        risk_score: Integer risk score in [0, 100].

    Returns:
        One of "critical", "elevated", or "monitor".
    """
    if risk_score > 90:
        return "critical"
    elif risk_score >= 40:
        return "elevated"
    else:
        return "monitor"


def calculate_risk_score(attack_confidence: float, asset_id: str) -> dict:
    """
    Calculate a risk score and tier for a given asset and attack confidence.

    Formula:
        risk_score = round(attack_confidence × (criticality / 10) × impact_weight × 100)

    The result is clamped to [0, 100] to guard against floating-point edge cases.

    Args:
        attack_confidence: Float in [0.0, 1.0] from the MITRE agent.
        asset_id:          String key looked up in asset_criticality_lookup.json.
                           Unknown IDs fall back to criticality=5, impact_weight=0.5.

    Returns:
        Dict with:
            risk_score (int 0-100),
            risk_tier  (str: "critical" | "elevated" | "monitor")

    Raises:
        FileNotFoundError: If asset_criticality_lookup.json is missing.
    """
    lookup = _load_asset_lookup()

    if asset_id not in lookup:
        logger.warning(
            f"Asset '{asset_id}' not found in criticality lookup. "
            f"Applying default: criticality={_UNKNOWN_ASSET_DEFAULT['criticality']}, "
            f"impact_weight={_UNKNOWN_ASSET_DEFAULT['impact_weight']}"
        )
        asset_data = _UNKNOWN_ASSET_DEFAULT
    else:
        asset_data = lookup[asset_id]

    criticality: int = asset_data["criticality"]
    impact_weight: float = asset_data["impact_weight"]

    raw = attack_confidence * (criticality / 10) * impact_weight * 100
    risk_score: int = int(max(0, min(100, round(raw))))

    risk_tier: RiskTier = _assign_tier(risk_score)

    logger.info(
        f"[risk_engine] asset={asset_id!r} attack_confidence={attack_confidence:.3f} "
        f"criticality={criticality} impact_weight={impact_weight} "
        f"→ risk_score={risk_score} tier={risk_tier}"
    )

    return {"risk_score": risk_score, "risk_tier": risk_tier}
