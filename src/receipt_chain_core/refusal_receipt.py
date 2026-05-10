"""Refusal Receipt — typed projection of a refusal-class ChainedReceipt.

Schema id: receipt_chain_core.refusal_receipt.v0.1

Provides:
    REFUSAL_VERDICTS              — frozenset of refusal-class Verdict values
    REFUSAL_RECEIPT_SCHEMA_ID     — schema identifier string
    to_refusal_receipt            — project a ChainedReceipt -> refusal receipt dict
    validate_refusal_receipt      — validate a refusal receipt dict shape (shape only)
    verify_refusal_receipt_hash   — validate shape + check receipt_hash consistency

Proves:
    receipt-chain-core can project a refusal-class ChainedReceipt into a
    typed refusal receipt shape, validate that shape, and detect post-projection
    mutation by recomputing and checking receipt_hash on demonstrated paths.

Does not prove:
    Cryptographic signature, authorship identity, legal admissibility,
    production readiness, path-universal coverage, or full runtime governance
    fabric.

Open follow-up:
    Issue #8 — Add optional signature verification for refusal receipts.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .hashing import sha256_hex
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

# Fields that form the canonical body for hash derivation.
# receipt_hash is excluded — it is the hash of everything else.
_BODY_FIELDS = tuple(f for f in _REQUIRED_FIELDS if f != "receipt_hash")

_REFUSAL_VERDICT_VALUES: frozenset[str] = frozenset(
    v.value for v in REFUSAL_VERDICTS
)


def to_refusal_receipt(receipt: ChainedReceipt) -> Dict[str, Any]:
    """Project a refusal-class ChainedReceipt into a refusal receipt dict.

    Raises ValueError if the receipt verdict is ALLOW.
    The returned dict matches the schema at schemas/refusal-receipt.schema.json.
    receipt_hash is the SHA-256 of the canonical JSON of all body fields.
    """
    if receipt.verdict not in REFUSAL_VERDICTS:
        raise ValueError(
            f"cannot project ALLOW receipt as refusal receipt; "
            f"verdict was {receipt.verdict.value!r}"
        )
    body: Dict[str, Any] = {
        "schema": REFUSAL_RECEIPT_SCHEMA_ID,
        "receipt_type": "refusal_receipt",
        "decision_id": receipt.decision_id,
        "issued_at": receipt.issued_at,
        "prior_chain_state_hash": receipt.prev_receipt_hash,
        "proposed_action": dict(receipt.proposed_action),
        "verdict": receipt.verdict.value,
        "reason_code": receipt.reason_code,
        "reason": receipt.reason,
        "does_not_execute": receipt.does_not_execute,
        "does_not_bind_consequence": receipt.does_not_bind_consequence,
    }
    # receipt_hash is derived from the body, not forwarded from ChainedReceipt.
    # This ensures the refusal receipt hash reflects the refusal receipt body,
    # not the underlying chain receipt hash.
    body["receipt_hash"] = sha256_hex({k: body[k] for k in _BODY_FIELDS})
    return body


def validate_refusal_receipt(data: Mapping[str, Any]) -> bool:
    """Validate a refusal receipt dict against the required shape.

    Shape validation only — does not check hash consistency.
    For hash consistency, call verify_refusal_receipt_hash().

    Returns True for a valid shape.
    Raises ValueError for any structural violation.

    Checks:
    - All required fields present
    - No extra fields
    - schema == REFUSAL_RECEIPT_SCHEMA_ID
    - receipt_type == 'refusal_receipt'
    - verdict is a refusal-class value
    - receipt_hash is a non-empty string
    - prior_chain_state_hash is None or a non-empty string
    - does_not_execute is True
    - does_not_bind_consequence is True
    - proposed_action contains action_type and object_id
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


def verify_refusal_receipt_hash(data: Mapping[str, Any]) -> bool:
    """Validate shape and verify that receipt_hash matches the canonical body.

    Calls validate_refusal_receipt(data) first, then re-derives receipt_hash
    from the body fields (all required fields except receipt_hash itself) and
    compares to data['receipt_hash'].

    Returns True if shape is valid and hash matches.
    Raises ValueError if shape is invalid or hash does not match.

    This detects post-projection mutation of any body field.
    It does not verify cryptographic signatures.
    See Issue #8 for signature verification.
    """
    # Shape check first — raises ValueError on any structural violation
    validate_refusal_receipt(data)

    # Re-derive hash from body fields
    body = {k: data[k] for k in _BODY_FIELDS}
    expected_hash = sha256_hex(body)

    if data["receipt_hash"] != expected_hash:
        raise ValueError(
            f"receipt_hash mismatch: stored hash does not match canonical body. "
            f"The receipt may have been mutated after projection."
        )

    return True
