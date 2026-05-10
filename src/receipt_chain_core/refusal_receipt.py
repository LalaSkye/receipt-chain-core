"""Refusal Receipt — typed projection of a refusal-class ChainedReceipt.

Schema id (unsigned): receipt_chain_core.refusal_receipt.v0.1
Schema id (signed):   receipt_chain_core.refusal_receipt.v0.2

Provides:
    REFUSAL_VERDICTS                  — frozenset of refusal-class Verdict values
    REFUSAL_RECEIPT_SCHEMA_ID         — unsigned schema identifier string
    SIGNED_REFUSAL_RECEIPT_SCHEMA_ID  — signed schema identifier string
    SIGNATURE_FIELDS                  — fields added by sign_refusal_receipt()
    to_refusal_receipt                — project a ChainedReceipt -> refusal receipt dict
    validate_refusal_receipt          — validate unsigned refusal receipt shape (shape only)
    verify_refusal_receipt_hash       — validate shape + check receipt_hash consistency
    validate_signed_refusal_receipt   — validate signed refusal receipt shape
    sign_refusal_receipt              — sign a validated, hash-verified receipt (Ed25519)
    verify_refusal_receipt_signature  — verify Ed25519 signature over receipt body

Proves:
    receipt-chain-core can project a refusal-class ChainedReceipt into a
    typed refusal receipt shape, validate that shape, detect post-projection
    mutation by recomputing and checking receipt_hash, and optionally verify
    an Ed25519 signature over the receipt body on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal admissibility,
    production security, compliance, adoption, field standard, or full runtime
    governance fabric.

Signature layer note:
    Signing requires a pre-validated, hash-verified v0.1 receipt as input.
    The signature covers canonical JSON of the v0.1 body (all required fields
    including receipt_hash), excluding signature fields themselves.
    A signed receipt is a v0.2 profile — a distinct type from the v0.1 unsigned
    receipt. Unsigned v0.1 receipts remain fully valid under the unsigned profile.
    Signature verification does not replace hash verification.
    Both layers must pass independently.

Open follow-up:
    Issue #11 visibility — add Scenario 8 and V11 to run_demo.py and
    verify_chain_invariants.py after this module+test PR is merged.
"""

from __future__ import annotations

import binascii
from typing import Any, Dict, Mapping, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False
    Ed25519PrivateKey = None  # type: ignore[assignment,misc]
    Ed25519PublicKey = None   # type: ignore[assignment,misc]

from .hashing import canonical_json, sha256_hex
from .receipt import ChainedReceipt
from .verdict import Verdict


REFUSAL_RECEIPT_SCHEMA_ID = "receipt_chain_core.refusal_receipt.v0.1"
SIGNED_REFUSAL_RECEIPT_SCHEMA_ID = "receipt_chain_core.refusal_receipt.v0.2"

REFUSAL_VERDICTS: frozenset[Verdict] = frozenset({
    Verdict.DENY,
    Verdict.HOLD,
    Verdict.REBIND_REQUIRED,
})

# Fields added by sign_refusal_receipt().
# These are excluded from the signing body and from validate_refusal_receipt().
SIGNATURE_FIELDS = ("signature", "signature_algorithm", "public_key_id")

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


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

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
    body["receipt_hash"] = sha256_hex({k: body[k] for k in _BODY_FIELDS})
    return body


# ---------------------------------------------------------------------------
# Unsigned v0.1 validation
# ---------------------------------------------------------------------------

def validate_refusal_receipt(data: Mapping[str, Any]) -> bool:
    """Validate a refusal receipt dict against the required shape.

    Shape validation only — does not check hash consistency.
    For hash consistency, call verify_refusal_receipt_hash().
    For signed receipts (v0.2), call validate_signed_refusal_receipt().

    Returns True for a valid shape.
    Raises ValueError for any structural violation.

    Checks:
    - All required fields present
    - No extra fields (signature fields cause failure — use validate_signed_refusal_receipt)
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

    known_fields = set(_REQUIRED_FIELDS)
    extra = set(data.keys()) - known_fields
    if extra:
        raise ValueError(f"refusal receipt contains unexpected fields: {sorted(extra)}")

    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(f"refusal receipt missing required fields: {missing}")

    if data["schema"] != REFUSAL_RECEIPT_SCHEMA_ID:
        raise ValueError(
            f"wrong schema: expected {REFUSAL_RECEIPT_SCHEMA_ID!r}, "
            f"got {data['schema']!r}"
        )

    if data["receipt_type"] != "refusal_receipt":
        raise ValueError(
            f"wrong receipt_type: expected 'refusal_receipt', "
            f"got {data['receipt_type']!r}"
        )

    if data["verdict"] not in _REFUSAL_VERDICT_VALUES:
        raise ValueError(
            f"verdict {data['verdict']!r} is not a refusal-class verdict; "
            f"allowed: {sorted(_REFUSAL_VERDICT_VALUES)}"
        )

    if not isinstance(data["receipt_hash"], str) or not data["receipt_hash"]:
        raise ValueError("receipt_hash must be a non-empty string")

    pcs = data["prior_chain_state_hash"]
    if pcs is not None:
        if not isinstance(pcs, str) or not pcs:
            raise ValueError(
                "prior_chain_state_hash must be None or a non-empty string"
            )

    if data["does_not_execute"] is not True:
        raise ValueError("does_not_execute must be True")
    if data["does_not_bind_consequence"] is not True:
        raise ValueError("does_not_bind_consequence must be True")

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
    from the body fields and compares to data['receipt_hash'].

    Returns True if shape is valid and hash matches.
    Raises ValueError if shape is invalid or hash does not match.

    This detects post-projection mutation of any body field.
    It does not verify cryptographic signatures.
    Signature verification is a separate, subsequent layer — see
    verify_refusal_receipt_signature().
    """
    validate_refusal_receipt(data)

    body = {k: data[k] for k in _BODY_FIELDS}
    expected_hash = sha256_hex(body)

    if data["receipt_hash"] != expected_hash:
        raise ValueError(
            f"receipt_hash mismatch: stored hash does not match canonical body. "
            f"The receipt may have been mutated after projection."
        )

    return True


# ---------------------------------------------------------------------------
# Signed v0.2 validation
# ---------------------------------------------------------------------------

_SIGNED_REQUIRED_FIELDS = _REQUIRED_FIELDS + ("signature", "signature_algorithm")
_SIGNED_OPTIONAL_FIELDS = ("public_key_id",)
_SIGNED_KNOWN_FIELDS = set(_SIGNED_REQUIRED_FIELDS) | set(_SIGNED_OPTIONAL_FIELDS)


def validate_signed_refusal_receipt(data: Mapping[str, Any]) -> bool:
    """Validate a signed refusal receipt dict (v0.2 profile) shape.

    Shape validation only — does not verify the cryptographic signature.
    For signature verification, call verify_refusal_receipt_signature().

    Returns True for a valid shape.
    Raises ValueError for any structural violation.

    Checks all v0.1 body fields (except schema/receipt_type constants),
    plus:
    - schema == SIGNED_REFUSAL_RECEIPT_SCHEMA_ID
    - receipt_type == 'signed_refusal_receipt'
    - signature is a non-empty string
    - signature_algorithm == 'Ed25519'
    - public_key_id is None or a non-empty string (optional field)
    """
    if not isinstance(data, Mapping):
        raise ValueError("signed refusal receipt must be a mapping")

    extra = set(data.keys()) - _SIGNED_KNOWN_FIELDS
    if extra:
        raise ValueError(
            f"signed refusal receipt contains unexpected fields: {sorted(extra)}"
        )

    missing = [f for f in _SIGNED_REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"signed refusal receipt missing required fields: {missing}"
        )

    if data["schema"] != SIGNED_REFUSAL_RECEIPT_SCHEMA_ID:
        raise ValueError(
            f"wrong schema: expected {SIGNED_REFUSAL_RECEIPT_SCHEMA_ID!r}, "
            f"got {data['schema']!r}"
        )

    if data["receipt_type"] != "signed_refusal_receipt":
        raise ValueError(
            f"wrong receipt_type: expected 'signed_refusal_receipt', "
            f"got {data['receipt_type']!r}"
        )

    if data["verdict"] not in _REFUSAL_VERDICT_VALUES:
        raise ValueError(
            f"verdict {data['verdict']!r} is not a refusal-class verdict; "
            f"allowed: {sorted(_REFUSAL_VERDICT_VALUES)}"
        )

    if not isinstance(data["receipt_hash"], str) or not data["receipt_hash"]:
        raise ValueError("receipt_hash must be a non-empty string")

    pcs = data["prior_chain_state_hash"]
    if pcs is not None:
        if not isinstance(pcs, str) or not pcs:
            raise ValueError(
                "prior_chain_state_hash must be None or a non-empty string"
            )

    if data["does_not_execute"] is not True:
        raise ValueError("does_not_execute must be True")
    if data["does_not_bind_consequence"] is not True:
        raise ValueError("does_not_bind_consequence must be True")

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

    if not isinstance(data["signature"], str) or not data["signature"]:
        raise ValueError("signature must be a non-empty string")

    if data["signature_algorithm"] != "Ed25519":
        raise ValueError(
            f"signature_algorithm must be 'Ed25519', "
            f"got {data['signature_algorithm']!r}"
        )

    if "public_key_id" in data:
        pkid = data["public_key_id"]
        if pkid is not None:
            if not isinstance(pkid, str) or not pkid:
                raise ValueError(
                    "public_key_id must be None or a non-empty string"
                )

    return True


# ---------------------------------------------------------------------------
# Signing body helpers
# ---------------------------------------------------------------------------

def _signing_body(data: Mapping[str, Any]) -> bytes:
    """Return canonical UTF-8 bytes of the v0.1 body to sign or verify.

    The signing body is the canonical JSON of the unsigned v0.1 receipt dict,
    which includes all _REQUIRED_FIELDS (including receipt_hash) and excludes
    all SIGNATURE_FIELDS.

    Because receipt_hash is inside the signing body, the signature covers both
    the receipt body content and its hash integrity in a single envelope.
    """
    body = {k: data[k] for k in _REQUIRED_FIELDS if k in data}
    return canonical_json(body).encode("utf-8")


# ---------------------------------------------------------------------------
# sign_refusal_receipt
# ---------------------------------------------------------------------------

def sign_refusal_receipt(
    data: Mapping[str, Any],
    private_key: "Ed25519PrivateKey",
    public_key_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sign a validated, hash-verified refusal receipt with an Ed25519 key.

    Requires:
        cryptography>=42.0 (install with: pip install receipt-chain-core[signature])

    Verification order enforced:
        1. validate_refusal_receipt(data)       — shape check
        2. verify_refusal_receipt_hash(data)    — hash consistency check
        3. sign                                  — only if both pass

    The signature covers canonical JSON of all v0.1 required fields (including
    receipt_hash), excluding signature fields. This means the signature binds
    the receipt body and its hash in a single envelope.

    Returns a new signed receipt dict (v0.2 profile). Does not mutate data.

    The returned dict must be validated with validate_signed_refusal_receipt()
    and its signature verified with verify_refusal_receipt_signature().

    Does not prove: legal identity, human authority, institutional authority,
    legal admissibility, production security, compliance, adoption, or field
    standard status.
    """
    if not _CRYPTO_AVAILABLE:
        raise ImportError(
            "cryptography package is required for signature support. "
            "Install with: pip install 'receipt-chain-core[signature]'"
        )

    # Enforce verification order — raises ValueError on any failure
    verify_refusal_receipt_hash(data)

    sig_bytes = private_key.sign(_signing_body(data))
    sig_hex = sig_bytes.hex()

    signed: Dict[str, Any] = {
        "schema": SIGNED_REFUSAL_RECEIPT_SCHEMA_ID,
        "receipt_type": "signed_refusal_receipt",
        "decision_id": data["decision_id"],
        "issued_at": data["issued_at"],
        "prior_chain_state_hash": data["prior_chain_state_hash"],
        "proposed_action": dict(data["proposed_action"]),
        "verdict": data["verdict"],
        "reason_code": data["reason_code"],
        "reason": data["reason"],
        "receipt_hash": data["receipt_hash"],
        "does_not_execute": data["does_not_execute"],
        "does_not_bind_consequence": data["does_not_bind_consequence"],
        "signature": sig_hex,
        "signature_algorithm": "Ed25519",
        "public_key_id": public_key_id,
    }
    return signed


# ---------------------------------------------------------------------------
# verify_refusal_receipt_signature
# ---------------------------------------------------------------------------

def verify_refusal_receipt_signature(
    data: Mapping[str, Any],
    public_key: "Ed25519PublicKey",
) -> bool:
    """Verify the Ed25519 signature on a signed refusal receipt.

    Requires:
        cryptography>=42.0 (install with: pip install receipt-chain-core[signature])

    Verification order enforced:
        1. validate_signed_refusal_receipt(data)  — shape check (v0.2 profile)
        2. verify receipt_hash consistency         — hash of v0.1 body fields
        3. verify signature                        — Ed25519 over signing body

    Returns True if all three checks pass.
    Raises ValueError if shape is invalid, hash is inconsistent, signature is
    missing or malformed, or the public key does not verify the signature.

    This does not prove: legal identity, human authority, institutional authority,
    legal admissibility, production security, compliance, adoption, or field
    standard status. It proves only that the supplied public key verifies the
    Ed25519 signature over this receipt body, and that the body has not changed
    since signing.
    """
    if not _CRYPTO_AVAILABLE:
        raise ImportError(
            "cryptography package is required for signature support. "
            "Install with: pip install 'receipt-chain-core[signature]'"
        )

    # Shape check (v0.2 profile)
    validate_signed_refusal_receipt(data)

    # Hash consistency check over v0.1 body fields
    body_for_hash = {k: data[k] for k in _REQUIRED_FIELDS}
    expected_hash = sha256_hex({k: body_for_hash[k] for k in _BODY_FIELDS})
    if data["receipt_hash"] != expected_hash:
        raise ValueError(
            "receipt_hash mismatch: stored hash does not match canonical body. "
            "The receipt may have been mutated after signing."
        )

    # Signature verification
    try:
        sig_bytes = binascii.unhexlify(data["signature"])
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"signature field is not valid hex: {exc}") from exc

    signing_body_bytes = _signing_body(data)

    try:
        public_key.verify(sig_bytes, signing_body_bytes)
    except Exception as exc:
        raise ValueError(
            f"Ed25519 signature verification failed: {exc}"
        ) from exc

    return True
