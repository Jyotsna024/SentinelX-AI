"""
commander_agent.py — SentinelX AI Phase 2 / Agent 3 (Commander)
=================================================================
Rule-based incident commander: selects a recommended action list from a
fixed menu based on the risk tier produced by risk_engine.py.

No LLM call is made here. The mapping is intentionally deterministic and
auditable — every tier always produces the same action set.

Action menu (full list, per spec):
    block_ip, disable_account, isolate_endpoint, snapshot_vm, notify_soc

Tier → action subset:
    critical  → all 5 actions  (maximum containment)
    elevated  → block_ip, snapshot_vm, notify_soc  (moderate containment)
    monitor   → []  (observe only, no active response)

approval_required:
    True  for critical and elevated  (human sign-off before execution)
    False for monitor               (auto-approved, no action taken)
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

RiskTier = Literal["critical", "elevated", "monitor"]

# ── Fixed action subsets per tier ──────────────────────────────────────────────
_ACTION_MAP: dict[str, list[str]] = {
    "critical": [
        "block_ip",
        "disable_account",
        "isolate_endpoint",
        "snapshot_vm",
        "notify_soc",
    ],
    "elevated": [
        "block_ip",
        "snapshot_vm",
        "notify_soc",
    ],
    "monitor": [],
}

_APPROVAL_MAP: dict[str, bool] = {
    "critical": True,
    "elevated": True,
    "monitor": False,
}


def get_actions(risk_tier: str) -> dict:
    """
    Return the recommended containment actions and approval requirement for a tier.

    This is a pure rule-based mapping — identical input always produces
    identical output, with no randomness or LLM inference involved.

    Args:
        risk_tier: One of "critical", "elevated", or "monitor".
                   Unrecognised tiers are treated as "monitor" with a warning.

    Returns:
        Dict with:
            recommended_actions (list[str]): Ordered list of action identifiers.
            approval_required   (bool):      True if a human must approve before
                                             execution; False for auto-approved.
    """
    normalised_tier = risk_tier.lower() if risk_tier else "monitor"

    if normalised_tier not in _ACTION_MAP:
        logger.warning(
            f"Unrecognised risk_tier '{risk_tier}'. "
            "Defaulting to 'monitor' (no actions, no approval required)."
        )
        normalised_tier = "monitor"

    recommended_actions = _ACTION_MAP[normalised_tier]
    approval_required = _APPROVAL_MAP[normalised_tier]

    logger.info(
        f"[commander] risk_tier={normalised_tier!r} "
        f"actions={recommended_actions} "
        f"approval_required={approval_required}"
    )

    return {
        "recommended_actions": recommended_actions,
        "approval_required": approval_required,
    }
