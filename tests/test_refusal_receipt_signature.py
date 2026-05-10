"""Tests for optional Ed25519 signature verification on refusal receipts.

Proves:
    receipt-chain-core can optionally verify an Ed25519 signature over a
    typed refusal receipt body on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal admissibility,
    production security, compliance, adoption, field standard, or full runtime
    governance fabric.

Signature layer note:
    Signing requires a pre-validated, hash-verified v0.1 receipt as input.
    Signature verification does not replace hash verification.
    Both layers are tested separately here.
    Unsigned v0.1 receipts remain fully valid; no regression introduced.
"""

from __future__ import annotations

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from receipt_chain_core.receipt import ChainedReceipt
from receipt_chain_core.verdict import Verdict
from receipt_chain_core.refusal_receipt import (
    REFUSAL_RECEIPT_SCHEMA_ID,
    SIGNED_REFUSAL_RECEIPT_SCHEMA_ID,
    to_refusal_receipt,
    validate_refusal_receipt,
    verify_refusal_receipt_hash,
    validate_signed_refusal_receipt,
    sign_refusal_receipt,
    verify_refusal_receipt_signature,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def keypair():
    """Generate a fresh Ed25519 keypair for the test module."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def wrong_keypair():
    """Generate a second, distinct Ed25519 keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def _make_receipt(
    verdict: Verdict = Verdict.DENY,
    sequence: int = 0,
    prev_receipt_hash: str | None = None,
) -> ChainedReceipt:
    return ChainedReceipt.build(
        sequence=sequence,
        prev_receipt_hash=prev_receipt_hash,
        decision_id=f"sig-test-{verdict.value.lower()}",
        proposed_action={"action_type": "write", "object_id": "obj-sig-001"},
        verdict=verdict,
        reason_code="SIG_TEST_REASON",
        reason="Signature test reason.",
        issued_at="2026-05-10T10:00:00Z",
    )


# ===========================================================================
# Test 1 — unsigned v0.1 receipt still passes shape validation (no regression)
# ===========================================================================

def test_unsigned_receipt_still_passes_shape_validation():
    """Unsigned v0.1 receipts are unaffected by signature layer additions."""
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["schema"] == REFUSAL_RECEIPT_SCHEMA_ID


# ===========================================================================
# Test 2 — unsigned v0.1 receipt still passes hash verification (no regression)
# ===========================================================================

def test_unsigned_receipt_still_passes_hash_verification():
    """Hash verification on unsigned v0.1 receipts is unaffected."""
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    assert verify_refusal_receipt_hash(projected) is True


# ===========================================================================
# Test 3 — signed receipt verifies with correct public key
# ===========================================================================

def test_signed_receipt_verifies_with_correct_key(keypair):
    private_key, public_key = keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    assert validate_signed_refusal_receipt(signed) is True
    assert signed["schema"] == SIGNED_REFUSAL_RECEIPT_SCHEMA_ID
    assert signed["receipt_type"] == "signed_refusal_receipt"
    assert signed["signature_algorithm"] == "Ed25519"
    assert verify_refusal_receipt_signature(signed, public_key) is True


# ===========================================================================
# Test 4 — signed receipt fails with wrong public key
# ===========================================================================

def test_signed_receipt_fails_with_wrong_key(keypair, wrong_keypair):
    private_key, _ = keypair
    _, wrong_public_key = wrong_keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    with pytest.raises(ValueError, match="Ed25519 signature verification failed"):
        verify_refusal_receipt_signature(signed, wrong_public_key)


# ===========================================================================
# Test 5 — signed receipt fails after reason_code mutation
# ===========================================================================

def test_signed_receipt_fails_after_reason_code_mutation(keypair):
    private_key, public_key = keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    mutated = dict(signed)
    mutated["reason_code"] = "MUTATED_REASON_CODE"

    # Shape still valid (reason_code is a non-empty string)
    assert validate_signed_refusal_receipt(mutated) is True

    # Hash check inside verify_refusal_receipt_signature catches body mutation
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_signature(mutated, public_key)


# ===========================================================================
# Test 6 — signed receipt fails after proposed_action mutation
# ===========================================================================

def test_signed_receipt_fails_after_proposed_action_mutation(keypair):
    private_key, public_key = keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    mutated = dict(signed)
    mutated["proposed_action"] = dict(signed["proposed_action"])
    mutated["proposed_action"]["object_id"] = "MUTATED_OBJECT"

    # Hash check catches the body mutation before signature check
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_signature(mutated, public_key)


# ===========================================================================
# Test 7 — malformed signature fails
# ===========================================================================

def test_malformed_signature_fails(keypair):
    private_key, public_key = keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    mutated = dict(signed)
    mutated["signature"] = "not_valid_hex_zzzz"

    with pytest.raises(ValueError, match="not valid hex"):
        verify_refusal_receipt_signature(mutated, public_key)


# ===========================================================================
# Test 8 — missing signature fails only when signature verification is requested
#           unsigned v0.1 receipt remains valid under unsigned profile
# ===========================================================================

def test_missing_signature_fails_only_when_signature_verification_requested():
    """An unsigned receipt is valid under validate_refusal_receipt.
    It fails validate_signed_refusal_receipt (missing signature field).
    Signature verification is not triggered by the unsigned profile path.
    This demonstrates that the two profiles are separate and non-overlapping.
    """
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)

    # Unsigned profile: passes
    assert validate_refusal_receipt(projected) is True
    assert verify_refusal_receipt_hash(projected) is True

    # Signed profile shape check: fails (signature field missing)
    with pytest.raises(ValueError, match="missing required fields"):
        validate_signed_refusal_receipt(projected)


# ===========================================================================
# Test 9 — sign_refusal_receipt does not mutate the original receipt dict
# ===========================================================================

def test_sign_does_not_mutate_original(keypair):
    private_key, _ = keypair
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    original_keys = set(projected.keys())
    original_schema = projected["schema"]

    _ = sign_refusal_receipt(projected, private_key)

    assert set(projected.keys()) == original_keys
    assert projected["schema"] == original_schema
    assert "signature" not in projected


# ===========================================================================
# Test 10 — signature verification does not replace hash verification
#            hash check runs inside verify_refusal_receipt_signature
#            and is not skipped even if signature would otherwise pass
# ===========================================================================

def test_signature_verification_does_not_replace_hash_verification(keypair):
    """Demonstrates that hash verification and signature verification are separate.

    A receipt mutated after signing will fail hash verification inside
    verify_refusal_receipt_signature, before the signature check is reached.
    Both layers must pass independently.
    """
    private_key, public_key = keypair
    receipt = _make_receipt(Verdict.HOLD)
    projected = to_refusal_receipt(receipt)
    signed = sign_refusal_receipt(projected, private_key)

    # Mutate the receipt body without updating receipt_hash
    mutated = dict(signed)
    mutated["reason"] = "This reason was changed after signing."

    # Hash check fires first inside verify_refusal_receipt_signature
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_signature(mutated, public_key)

    # The unsigned v0.1 path is also unaffected — hash verifier still works
    # independently on the original projected receipt
    assert verify_refusal_receipt_hash(projected) is True
