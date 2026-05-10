"""Refusal Receipt — typed projection of a refusal-class ChainedReceipt.

Schema id: receipt_chain_core.refusal_receipt.v0.1

Provides:
    REFUSAL_VERDICTS          — frozenset of refusal-class Verdict values
    REFUSAL_RECEIPT_SCHEMA_ID — schema identifier string
    to_refusal_receipt        — project a ChainedReceipt -> refusal receipt dict
    validate_refusal_receipt  — validate a refusal receipt dict shape

Proves:
    receipt-chain-core can project a refusal-class ChainedReceipt into a
    typed refusal receipt shape and validate that shape on demonstrated paths.

Does not prove:
    Cryptographic signature, legal admissibility, production readiness,
    path-universal coverage, or full runtime governance fabric.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .receipt import ChainedReceipt
from .verdict import Verdict


REFUSAL_RECEIPT_SCHEMA_ID = "receipt_chain_core.refusal_receipt.v0.1"

REFUSAL_VERDICTS: frozenset[Verdict] = frozenset({
    Verdict.DENY,
    Verdict.HOLD,
    Verdict.REBIND_REQUIRED,
})

_REQUIRED_FIELDS = (
    "schema",
    "receipt_type",
    "decision_id",
    "issued_at",
    "prior_chain_state_hash",
    "proposed_action",
    "verdict",
    "reason_code",
    "reason",
    "receipt_hash",
    "does_not_execute",
    "does_not_bind_consequence",
)

_REFUSAL_VERDICT_VALUES: frozenset[str] = frozenset(
    v.value for v in REFUSAL_VERDICTS
)


def to_refusal_receipt(receipt: ChainedReceipt) -> Dict[str, Any]:
    """Project a refusal-class ChainedReceipt into a refusal receipt dict.

    Raises ValueError if the receipt verdict is ALLOW.
    The returned dict matches the schema at schemas/refusal-receipt.schema.json.
    """
    if receipt.verdict not in REFUSAL_VERDICTS:
        raise ValueError(
            f"cannot project ALLOW receipt as refusal receipt; "
            f"verdict was {receipt.verdict.value!r}"
        )
    return {
        "schema": REFUSAL_RECEIPT_SCHEMA_ID,
        "receipt_type": "refusal_receipt",
        "decision_id": receipt.decision_id,
        "issued_at": receipt.issued_at,
        "prior_chain_state_hash": receipt.prev_receipt_hash,
        "proposed_action": dict(receipt.proposed_action),
        "verdict": receipt.verdict.value,
        "reason_code": receipt.reason_code,
        "reason": receipt.reason,
        "receipt_hash": receipt.receipt_hash,
        "does_not_execute": receipt.does_not_execute,
        "does_not_bind_consequence": receipt.does_not_bind_consequence,
    }


def validate_refusal_receipt(data: Mapping[str, Any]) -> bool:
    """Validate a refusal receipt dict against the required shape.

    Returns True for a valid shape.
    Raises ValueError for any structural violation.

    Checks:
    - All required fields present
    - schema == REFUSAL_RECEIPT_SCHEMA_ID
    - receipt_type == 'refusal_receipt'
    - verdict is a refusal-class value
    - receipt_hash is a non-empty string
    - prior_chain_state_hash is None or a non-empty string
    - does_not_execute is True
    - does_not_bind_consequence is True
    - proposed_action contains action_type and object_id
    - No extra fields beyond the defined schema
    """
    if not isinstance(data, Mapping):
        raise ValueError("refusal receipt must be a mapping")

    # Check for extra fields first — fail-closed on unknown shape
    known_fields = set(_REQUIRED_FIELDS)
    extra = set(data.keys()) - known_fields
    if extra:
        raise ValueError(f"refusal receipt contains unexpected fields: {sorted(extra)}")

    # Required fields present
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(f"refusal receipt missing required fields: {missing}")

    # Fixed: schema
    if data["schema"] != REFUSAL_RECEIPT_SCHEMA_ID:
        raise ValueError(
            f"wrong schema: expected {REFUSAL_RECEIPT_SCHEMA_ID!r}, "
            f"got {data['schema']!r}"
        )

    # Fixed: receipt_type
    if data["receipt_type"] != "refusal_receipt":
        raise ValueError(
            f"wrong receipt_type: expected 'refusal_receipt', "
            f"got {data['receipt_type']!r}"
        )

    # Verdict must be refusal-class
    if data["verdict"] not in _REFUSAL_VERDICT_VALUES:
        raise ValueError(
            f"verdict {data['verdict']!r} is not a refusal-class verdict; "
            f"allowed: {sorted(_REFUSAL_VERDICT_VALUES)}"
        )

    # receipt_hash must be a non-empty string
    if not isinstance(data["receipt_hash"], str) or not data["receipt_hash"]:
        raise ValueError("receipt_hash must be a non-empty string")

    # prior_chain_state_hash: None or non-empty string
    pcs = data["prior_chain_state_hash"]
    if pcs is not None:
        if not isinstance(pcs, str) or not pcs:
            raise ValueError(
                "prior_chain_state_hash must be None or a non-empty string"
            )

    # Fixed flags
    if data["does_not_execute"] is not True:
        raise ValueError("does_not_execute must be True")
    if data["does_not_bind_consequence"] is not True:
        raise ValueError("does_not_bind_consequence must be True")

    # proposed_action structure
    action = data["proposed_action"]
    if not isinstance(action, Mapping):
        raise ValueError("proposed_action must be a mapping")
    for key in ("action_type", "object_id"):
        if key not in action:
            raise ValueError(f"proposed_action missing required key: {key!r}")
        if not isinstance(action[key], str) or not action[key]:
            raise ValueError(
                f"proposed_action.{key} must be a non-empty string"
            )

    return True
