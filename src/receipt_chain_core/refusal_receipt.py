"""Refusal Receipt — typed projection of a refusal-class ChainedReceipt.

Schema id: receipt_chain_core.refusal_receipt.v0.1

Provides:
    REFUSAL_VERDICTS              — frozenset of refusal-class Verdict values
    REFUSAL_RECEIPT_SCHEMA_ID     — schema identifier string
    to_refusal_receipt            — project a ChainedReceipt -> refusal receipt dict
    validate_refusal_receipt      — validate a refusal receipt dict shape (shape only)
    verify_refusal_receipt_hash   — validate shape + check receipt_hash consistency
    sign_refusal_receipt          — sign a refusal receipt body with Ed25519 (optional)
    verify_refusal_receipt_signature — verify Ed25519 signature over receipt body (optional)

Proves:
    receipt-chain-core can project a refusal-class ChainedReceipt into a
    typed refusal receipt shape, validate that shape, detect post-projection
    mutation by recomputing and checking receipt_hash, and optionally verify
    an Ed25519 signature over the canonical receipt body on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal admissibility,
    production security, compliance, adoption, field standard, or full runtime
    governance fabric.

Signature fields (optional, v0.1):
    signature           — base64url-encoded Ed25519 signature over canonical signing body
    signature_algorithm — fixed value "Ed25519"
    public_key_id       — optional caller-supplied key identifier string (label only,
                          not identity proof). Allowed only on signed receipts.

Signature field rules:
    unsigned receipt:  no signature, no signature_algorithm, no public_key_id
    signed receipt:    signature + signature_algorithm required together
    public_key_id:     allowed only when signature + signature_algorithm are present

PRIMARY DESIGN RULE:
    Hash before signature.
    Verification order: validate_refusal_receipt -> verify_refusal_receipt_hash ->
    verify_refusal_receipt_signature.

Dependency:
    cryptography (Ed25519 via hazmat.primitives.asymmetric.ed25519)
    Declared as optional extra [signature] in pyproject.toml.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, Mapping, Optional

from .hashing import canonical_json, sha256_hex
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

# Signature fields are optional. They are excluded from the canonical signing body
# so that signing does not change the hash and unsigned receipts remain valid.
_SIGNATURE_FIELDS = ("signature", "signature_algorithm", "public_key_id")

# All known fields = required + optional signature fields
_ALL_KNOWN_FIELDS = frozenset(_REQUIRED_FIELDS) | frozenset(_SIGNATURE_FIELDS)

_REFUSAL_VERDICT_VALUES: frozenset[str] = frozenset(
    v.value for v in REFUSAL_VERDICTS
)

_SIGNATURE_ALGORITHM = "Ed25519"


def to_refusal_receipt(receipt: ChainedReceipt) -> Dict[str, Any]:
    """Project a refusal-class ChainedReceipt into a refusal receipt dict.

    Raises ValueError if the receipt verdict is ALLOW.
    The returned dict matches the schema at schemas/refusal-receipt.schema.json.
    receipt_hash is the SHA-256 of the canonical JSON of all body fields.
    Returned dict contains no signature fields (unsigned v0.1 receipt).
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


def validate_refusal_receipt(data: Mapping[str, Any]) -> bool:
    """Validate a refusal receipt dict against the required shape.

    Shape validation only — does not check hash consistency or signature.
    For hash consistency, call verify_refusal_receipt_hash().
    For signature, call verify_refusal_receipt_signature().

    Accepts both unsigned receipts (no signature fields) and signed receipts
    (signature + signature_algorithm required together; public_key_id allowed
    only when both signature and signature_algorithm are present).

    Signature field rules:
        unsigned:     no signature, no signature_algorithm, no public_key_id
        signed:       signature + signature_algorithm required together
        public_key_id: allowed only on signed receipts (label only, not identity proof)

    Returns True for a valid shape.
    Raises ValueError for any structural violation.
    """
    if not isinstance(data, Mapping):
        raise ValueError("refusal receipt must be a mapping")

    # Check for extra fields — fail-closed on unknown shape
    extra = set(data.keys()) - _ALL_KNOWN_FIELDS
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

    # Signature field consistency rules:
    #
    # Rule 1: signature and signature_algorithm must both be present or both absent.
    # Rule 2: public_key_id is only allowed when signature + signature_algorithm are present.
    #
    # This closes the public_key_id-alone shape gap:
    # a receipt with public_key_id but no signature fields is rejected.
    # public_key_id is a label, not identity proof.
    has_sig = "signature" in data
    has_alg = "signature_algorithm" in data
    has_kid = "public_key_id" in data

    if has_kid and not (has_sig and has_alg):
        raise ValueError(
            "public_key_id is only allowed on signed receipts: "
            "signature and signature_algorithm must also be present"
        )

    if has_sig != has_alg:
        raise ValueError(
            "signature and signature_algorithm must both be present or both absent"
        )

    if has_sig:
        if not isinstance(data["signature"], str) or not data["signature"]:
            raise ValueError("signature must be a non-empty string")
        if data["signature_algorithm"] != _SIGNATURE_ALGORITHM:
            raise ValueError(
                f"signature_algorithm must be {_SIGNATURE_ALGORITHM!r}, "
                f"got {data['signature_algorithm']!r}"
            )
        if has_kid:
            pk_id = data["public_key_id"]
            if pk_id is not None and (not isinstance(pk_id, str) or not pk_id):
                raise ValueError(
                    "public_key_id must be None or a non-empty string"
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
    Call verify_refusal_receipt_signature() for signature verification.
    """
    validate_refusal_receipt(data)

    body = {k: data[k] for k in _BODY_FIELDS}
    expected_hash = sha256_hex(body)

    if data["receipt_hash"] != expected_hash:
        raise ValueError(
            "receipt_hash mismatch: stored hash does not match canonical body. "
            "The receipt may have been mutated after projection."
        )

    return True


def _canonical_signing_body(data: Mapping[str, Any]) -> bytes:
    """Return the canonical UTF-8 bytes of the signing body.

    The signing body is the canonical JSON of all fields excluding
    signature, signature_algorithm, and public_key_id.
    This ensures the signing body is identical for unsigned and signed receipts
    and that re-signing produces the same bytes.
    """
    body = {k: v for k, v in data.items() if k not in _SIGNATURE_FIELDS}
    return canonical_json(body).encode("utf-8")


def sign_refusal_receipt(
    data: Mapping[str, Any],
    private_key: Any,
    public_key_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sign a refusal receipt body with an Ed25519 private key.

    Verification order (PRIMARY DESIGN RULE — hash before signature):
        1. validate_refusal_receipt(data)
        2. verify_refusal_receipt_hash(data)
        3. sign canonical body bytes with Ed25519

    Args:
        data:          A valid, hash-verified refusal receipt dict (unsigned or signed).
        private_key:   An Ed25519PrivateKey instance from the cryptography library.
        public_key_id: Optional caller-supplied key identifier string (label only,
                       not identity proof).

    Returns:
        A new dict — original is not mutated — containing all original fields
        plus signature, signature_algorithm, and (if supplied) public_key_id.
        signature is base64url-encoded (no padding) per RFC 7515.

    Raises:
        ValueError if shape is invalid or hash does not match.
    """
    # Step 1 & 2: shape then hash (PRIMARY DESIGN RULE)
    validate_refusal_receipt(data)
    verify_refusal_receipt_hash(data)

    # Step 3: sign canonical body (excludes signature fields)
    signing_bytes = _canonical_signing_body(data)
    raw_signature: bytes = private_key.sign(signing_bytes)
    signature_b64 = base64.urlsafe_b64encode(raw_signature).rstrip(b"=").decode("ascii")

    # Build new dict — do not mutate original
    signed: Dict[str, Any] = dict(data)
    signed["signature"] = signature_b64
    signed["signature_algorithm"] = _SIGNATURE_ALGORITHM
    if public_key_id is not None:
        signed["public_key_id"] = public_key_id
    return signed


def verify_refusal_receipt_signature(
    data: Mapping[str, Any],
    public_key: Any,
) -> bool:
    """Verify the Ed25519 signature over a refusal receipt canonical body.

    Verification order (PRIMARY DESIGN RULE — hash before signature):
        1. validate_refusal_receipt(data)
        2. verify_refusal_receipt_hash(data)
        3. verify Ed25519 signature over canonical signing body

    Args:
        data:       A signed refusal receipt dict.
        public_key: An Ed25519PublicKey instance from the cryptography library.

    Returns:
        True if signature is present, well-formed, and valid.

    Raises:
        ValueError if:
            - shape is invalid
            - hash does not match
            - signature field is missing
            - signature is not valid base64url
            - signature does not verify (wrong key, mutated body, or forgery)
    """
    from cryptography.exceptions import InvalidSignature

    # Step 1 & 2: shape then hash (PRIMARY DESIGN RULE)
    validate_refusal_receipt(data)
    verify_refusal_receipt_hash(data)

    # Step 3: require signature fields
    if "signature" not in data:
        raise ValueError(
            "signature field is missing; call sign_refusal_receipt() first. "
            "verify_refusal_receipt_signature() does not replace "
            "verify_refusal_receipt_hash()."
        )

    # Decode base64url signature
    sig_str: str = data["signature"]
    try:
        # Restore padding for base64 decode
        padded = sig_str + "=" * (4 - len(sig_str) % 4) if len(sig_str) % 4 else sig_str
        raw_signature = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise ValueError(f"signature is not valid base64url: {exc}") from exc

    # Verify over canonical signing body
    signing_bytes = _canonical_signing_body(data)
    try:
        public_key.verify(raw_signature, signing_bytes)
    except InvalidSignature as exc:
        raise ValueError(
            "signature verification failed: wrong key, mutated body, or forged receipt"
        ) from exc

    return True
