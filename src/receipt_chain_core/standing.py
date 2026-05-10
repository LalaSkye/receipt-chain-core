"""Standing replay harness v0.1.

A tiny deterministic helper for checking whether the same proposed action
keeps standing when context conditions change.

This module is deliberately NON_EXEC. It produces verdicts and receipts. It
does not perform the proposed action and does not bind consequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from .chain import Chain
from .hashing import sha256_hex
from .receipt import ChainedReceipt
from .verdict import Verdict


STANDING_SCHEMA_ID = "receipt_chain_core.standing_replay.v0.1"


REQUIRED_CONTEXT_FIELDS = ("role", "scope", "risk_level", "time_state")


def _validate_context(context: Mapping[str, Any]) -> None:
    if not isinstance(context, Mapping):
        raise ValueError("context must be a mapping")
    missing = [k for k in REQUIRED_CONTEXT_FIELDS if k not in context]
    if missing:
        raise ValueError(f"context missing required fields: {missing}")
    for key in REQUIRED_CONTEXT_FIELDS:
        if not isinstance(context[key], str) or not context[key]:
            raise ValueError(f"context.{key} must be a non-empty string")


def _standing_reason(context: Mapping[str, Any]) -> Tuple[Verdict, str, str]:
    """Evaluate standing from the current context only.

    First-fail order is fixed for replay stability.
    """
    _validate_context(context)

    if context["time_state"] == "expired":
        return (
            Verdict.HOLD,
            "standing.time_expired",
            "proposed action lost standing because the authority window expired",
        )
    if context["scope"] in {"external_blocked", "out_of_scope"}:
        return (
            Verdict.HOLD,
            "standing.scope_changed",
            "proposed action lost standing because scope no longer permits it",
        )
    if context["risk_level"] in {"elevated", "high", "blocked"}:
        return (
            Verdict.HOLD,
            "standing.risk_changed",
            "proposed action lost standing because risk context changed",
        )
    return (
        Verdict.ALLOW,
        "standing.context_still_valid",
        "context conditions preserve standing for this proposed action",
    )


def bind_action_to_context(
    proposed_action: Mapping[str, Any], context: Mapping[str, Any]
) -> Dict[str, Any]:
    """Return the canonical action shape used by the receipt chain.

    The context hash lets replay prove which condition state was evaluated
    without expanding the base receipt schema.
    """
    _validate_context(context)
    return {
        "action_type": str(proposed_action["action_type"]),
        "object_id": str(proposed_action["object_id"]),
        "context_hash": sha256_hex(dict(context)),
        "standing_schema": STANDING_SCHEMA_ID,
    }


@dataclass(frozen=True)
class StandingReplayResult:
    """Result of one standing replay evaluation."""

    receipt: ChainedReceipt
    context_hash: str
    verdict: Verdict
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": STANDING_SCHEMA_ID,
            "context_hash": self.context_hash,
            "verdict": self.verdict.value,
            "reason_code": self.reason_code,
            "receipt": self.receipt.to_dict(),
        }


def evaluate_standing(
    chain: Chain,
    *,
    proposed_action: Mapping[str, Any],
    context: Mapping[str, Any],
    decision_id: str,
    issued_at: str,
) -> StandingReplayResult:
    """Evaluate whether a proposed action has standing under context.

    The receipt is appended to the supplied chain. Same proposed action and
    same context produce the same verdict and reason code.
    """
    verdict, reason_code, reason = _standing_reason(context)
    bound_action = bind_action_to_context(proposed_action, context)
    next_seq = (chain.head_sequence + 1) if chain.head_sequence is not None else 0
    prev_hash = chain.head_hash

    receipt = ChainedReceipt.build(
        sequence=next_seq,
        prev_receipt_hash=prev_hash,
        decision_id=decision_id,
        proposed_action=bound_action,
        verdict=verdict,
        reason_code=reason_code,
        reason=reason,
        issued_at=issued_at,
    )
    chain.append(receipt)

    return StandingReplayResult(
        receipt=receipt,
        context_hash=bound_action["context_hash"],
        verdict=verdict,
        reason_code=reason_code,
    )
