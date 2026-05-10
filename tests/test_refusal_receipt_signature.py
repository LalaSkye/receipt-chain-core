"""Tests for optional Ed25519 signature verification over refusal receipts.

Issue #8 — Add optional signature verification for refusal receipts.

Tests:
    1.  Unsigned refusal receipt passes shape validation.
    2.  Unsigned refusal receipt passes hash verification.
    3.  Signed refusal receipt verifies with correct public key.
    4.  Signed refusal receipt fails with wrong public key.
    5.  Signed refusal receipt fails after reason_code mutation.
    6.  Signed refusal receipt fails after proposed_action mutation.
    7.  Malformed signature fails.
    8.  Missing signature fails only when signature verification is requested.
    9.  sign_refusal_receipt does not mutate original receipt dict.
    10. Signature verification does not replace hash verification.

Design rule:
    Hash before signature.
    Verification order: validate -> hash -> signature.

Proves:
    receipt-chain-core can optionally verify an Ed25519 signature over a typed
    refusal receipt body on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal admissibility,
    production security, compliance, adoption, field standard, or full runtime
    governance fabric.
"""

from __future__ import annotations

import copy
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from receipt_chain_core.refusal_receipt import (
    sign_refusal_receipt,
    to_refusal_receipt,
    validate_refusal_receipt,
    verify_refusal_receipt_hash,
    verify_refusal_receipt_signature,
)
from receipt_chain_core.receipt import ChainedReceipt
from receipt_chain_core.verdict import Verdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ed25519_keypair():
    """Generate a fresh Ed25519 key pair for each test."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture()
def unsigned_refusal_receipt():
    """A valid unsigned v0.1 refusal receipt."""
    receipt = ChainedReceipt(
        decision_id="test-decision-sig-001",
        issued_at="2026-05-10T10:20:00Z",
        prev_receipt_hash="abc123def456",
        proposed_action={"action_type": "write", "object_id": "file://data.csv"},
        verdict=Verdict.DENY,
        reason_code="POLICY_VIOLATION",
        reason="Action refused by policy.",
        does_not_execute=True,
        does_not_bind_consequence=True,
    )
    return to_refusal_receipt(receipt)


# ---------------------------------------------------------------------------
# Test 1: Unsigned receipt passes shape validation
# ---------------------------------------------------------------------------

def test_unsigned_receipt_passes_shape_validation(unsigned_refusal_receipt):
    """Test 1: unsigned refusal receipt passes validate_refusal_receipt."""
    assert validate_refusal_receipt(unsigned_refusal_receipt) is True


# ---------------------------------------------------------------------------
# Test 2: Unsigned receipt passes hash verification
# ---------------------------------------------------------------------------

def test_unsigned_receipt_passes_hash_verification(unsigned_refusal_receipt):
    """Test 2: unsigned refusal receipt passes verify_refusal_receipt_hash."""
    assert verify_refusal_receipt_hash(unsigned_refusal_receipt) is True


# ---------------------------------------------------------------------------
# Test 3: Signed receipt verifies with correct public key
# ---------------------------------------------------------------------------

def test_signed_receipt_verifies_with_correct_key(unsigned_refusal_receipt, ed25519_keypair):
    """Test 3: signed receipt verifies correctly with the matching public key."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)
    assert verify_refusal_receipt_signature(signed, public_key) is True


# ---------------------------------------------------------------------------
# Test 4: Signed receipt fails with wrong public key
# ---------------------------------------------------------------------------

def test_signed_receipt_fails_with_wrong_key(unsigned_refusal_receipt, ed25519_keypair):
    """Test 4: signed receipt fails verification with a different public key."""
    private_key, _ = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    # Generate an unrelated key pair
    wrong_private_key = Ed25519PrivateKey.generate()
    wrong_public_key = wrong_private_key.public_key()

    with pytest.raises(ValueError, match="signature verification failed"):
        verify_refusal_receipt_signature(signed, wrong_public_key)


# ---------------------------------------------------------------------------
# Test 5: Signed receipt fails after reason_code mutation
# ---------------------------------------------------------------------------

def test_signed_receipt_fails_after_reason_code_mutation(unsigned_refusal_receipt, ed25519_keypair):
    """Test 5: signature verification fails if reason_code is mutated after signing."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    # Mutate reason_code in a copy — also need to recompute receipt_hash
    # to pass the hash check and reach the signature check.
    # If we mutate only reason_code without updating receipt_hash, the hash
    # check will catch it first. Both paths (hash or signature) must fail.
    mutated = dict(signed)
    mutated["reason_code"] = "MUTATED_CODE"
    # receipt_hash still matches old body — hash check fires first
    with pytest.raises(ValueError):
        verify_refusal_receipt_signature(mutated, public_key)


# ---------------------------------------------------------------------------
# Test 6: Signed receipt fails after proposed_action mutation
# ---------------------------------------------------------------------------

def test_signed_receipt_fails_after_proposed_action_mutation(unsigned_refusal_receipt, ed25519_keypair):
    """Test 6: signature verification fails if proposed_action is mutated after signing."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    mutated = dict(signed)
    mutated["proposed_action"] = {"action_type": "delete", "object_id": "file://other.csv"}
    # receipt_hash still reflects old body — hash check fires first
    with pytest.raises(ValueError):
        verify_refusal_receipt_signature(mutated, public_key)


# ---------------------------------------------------------------------------
# Test 6b: Signature catches mutation even when receipt_hash is also recomputed
# ---------------------------------------------------------------------------

def test_signature_catches_body_mutation_independent_of_hash(unsigned_refusal_receipt, ed25519_keypair):
    """Test 6b: if an attacker recomputes receipt_hash after mutation,
    signature verification still fails — the signature covers the original body.
    """
    from receipt_chain_core.hashing import sha256_hex
    from receipt_chain_core.refusal_receipt import _BODY_FIELDS

    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    # Attacker mutates reason_code and recomputes receipt_hash
    mutated = dict(signed)
    mutated["reason_code"] = "ATTACKER_CODE"
    # Recompute receipt_hash so hash check passes
    body_for_hash = {k: mutated[k] for k in _BODY_FIELDS}
    mutated["receipt_hash"] = sha256_hex(body_for_hash)

    # Hash check passes (attacker recomputed it), but signature should fail
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_refusal_receipt_signature(mutated, public_key)


# ---------------------------------------------------------------------------
# Test 7: Malformed signature fails
# ---------------------------------------------------------------------------

def test_malformed_signature_fails(unsigned_refusal_receipt, ed25519_keypair):
    """Test 7: a receipt with a malformed (not-base64url) signature raises ValueError."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    malformed = dict(signed)
    malformed["signature"] = "!!!not-valid-base64!!!"

    with pytest.raises(ValueError):
        verify_refusal_receipt_signature(malformed, public_key)


# ---------------------------------------------------------------------------
# Test 8: Missing signature fails only when signature verification is requested
# ---------------------------------------------------------------------------

def test_missing_signature_only_fails_for_signature_verification(unsigned_refusal_receipt, ed25519_keypair):
    """Test 8: unsigned receipt passes shape + hash checks but fails signature check."""
    _, public_key = ed25519_keypair

    # Shape and hash pass fine
    assert validate_refusal_receipt(unsigned_refusal_receipt) is True
    assert verify_refusal_receipt_hash(unsigned_refusal_receipt) is True

    # Signature check raises because signature is missing
    with pytest.raises(ValueError, match="signature field is missing"):
        verify_refusal_receipt_signature(unsigned_refusal_receipt, public_key)


# ---------------------------------------------------------------------------
# Test 9: sign_refusal_receipt does not mutate original dict
# ---------------------------------------------------------------------------

def test_sign_does_not_mutate_original(unsigned_refusal_receipt, ed25519_keypair):
    """Test 9: sign_refusal_receipt returns a new dict; original is unchanged."""
    private_key, _ = ed25519_keypair
    original_keys = set(unsigned_refusal_receipt.keys())
    original_copy = copy.deepcopy(unsigned_refusal_receipt)

    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    # Original is unchanged
    assert set(unsigned_refusal_receipt.keys()) == original_keys
    assert unsigned_refusal_receipt == original_copy

    # Signed is a different object with signature fields
    assert signed is not unsigned_refusal_receipt
    assert "signature" in signed
    assert "signature_algorithm" in signed
    assert "signature" not in unsigned_refusal_receipt


# ---------------------------------------------------------------------------
# Test 10: Signature verification does not replace hash verification
# ---------------------------------------------------------------------------

def test_signature_does_not_replace_hash_verification(unsigned_refusal_receipt, ed25519_keypair):
    """Test 10: verify_refusal_receipt_signature calls hash check internally;
    a receipt with a valid signature but corrupted receipt_hash still fails.
    """
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)

    # Corrupt receipt_hash in a copy
    corrupted = dict(signed)
    corrupted["receipt_hash"] = "0" * 64  # wrong hash, same length

    # hash check fires inside verify_refusal_receipt_signature before signature check
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_signature(corrupted, public_key)


# ---------------------------------------------------------------------------
# Test bonus: public_key_id is preserved and optional
# ---------------------------------------------------------------------------

def test_sign_with_public_key_id(unsigned_refusal_receipt, ed25519_keypair):
    """sign_refusal_receipt accepts and stores an optional public_key_id."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(
        unsigned_refusal_receipt, private_key, public_key_id="key-2026-05-10"
    )
    assert signed["public_key_id"] == "key-2026-05-10"
    assert verify_refusal_receipt_signature(signed, public_key) is True


def test_sign_without_public_key_id(unsigned_refusal_receipt, ed25519_keypair):
    """sign_refusal_receipt works without public_key_id; field absent in output."""
    private_key, public_key = ed25519_keypair
    signed = sign_refusal_receipt(unsigned_refusal_receipt, private_key)
    assert "public_key_id" not in signed
    assert verify_refusal_receipt_signature(signed, public_key) is True
