"""Tests for refusal receipt projection, shape validation, and hash consistency.

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

import pytest

from receipt_chain_core.receipt import ChainedReceipt
from receipt_chain_core.verdict import Verdict
from receipt_chain_core.refusal_receipt import (
    REFUSAL_RECEIPT_SCHEMA_ID,
    to_refusal_receipt,
    validate_refusal_receipt,
    verify_refusal_receipt_hash,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_receipt(
    verdict: Verdict,
    sequence: int = 0,
    prev_receipt_hash: str | None = None,
) -> ChainedReceipt:
    """Build a minimal ChainedReceipt for the given verdict."""
    return ChainedReceipt.build(
        sequence=sequence,
        prev_receipt_hash=prev_receipt_hash,
        decision_id=f"test-decision-{verdict.value.lower()}",
        proposed_action={"action_type": "write", "object_id": "obj-001"},
        verdict=verdict,
        reason_code="TEST_REASON",
        reason="Test reason for this verdict.",
        issued_at="2026-05-10T10:00:00Z",
    )


# ===========================================================================
# SECTION A — Shape validation (validate_refusal_receipt)
# These tests prove the shape contract. They do not touch hash consistency.
# ===========================================================================

# ---------------------------------------------------------------------------
# A1. HOLD receipt produces valid refusal receipt shape
# ---------------------------------------------------------------------------

def test_hold_produces_valid_refusal_receipt():
    receipt = _make_receipt(Verdict.HOLD)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["verdict"] == "HOLD"
    assert projected["receipt_type"] == "refusal_receipt"
    assert projected["schema"] == REFUSAL_RECEIPT_SCHEMA_ID
    assert projected["does_not_execute"] is True
    assert projected["does_not_bind_consequence"] is True
    assert projected["prior_chain_state_hash"] is None  # sequence 0


# ---------------------------------------------------------------------------
# A2. DENY receipt produces valid refusal receipt shape
# ---------------------------------------------------------------------------

def test_deny_produces_valid_refusal_receipt():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["verdict"] == "DENY"


# ---------------------------------------------------------------------------
# A3. REBIND_REQUIRED receipt produces valid refusal receipt shape
# ---------------------------------------------------------------------------

def test_rebind_required_produces_valid_refusal_receipt():
    receipt = _make_receipt(Verdict.REBIND_REQUIRED)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["verdict"] == "REBIND_REQUIRED"


# ---------------------------------------------------------------------------
# A4. ALLOW receipt cannot be projected as refusal receipt
# ---------------------------------------------------------------------------

def test_allow_cannot_be_projected_as_refusal_receipt():
    receipt = _make_receipt(Verdict.ALLOW)
    with pytest.raises(ValueError, match="cannot project ALLOW receipt"):
        to_refusal_receipt(receipt)


# ---------------------------------------------------------------------------
# A5. Missing required field fails shape validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", [
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
])
def test_missing_required_field_fails_validation(field: str):
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    del projected[field]
    with pytest.raises(ValueError):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A6. Wrong receipt_type fails shape validation
# ---------------------------------------------------------------------------

def test_wrong_receipt_type_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["receipt_type"] = "allow_receipt"
    with pytest.raises(ValueError, match="wrong receipt_type"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A7. Wrong verdict fails shape validation
# ---------------------------------------------------------------------------

def test_wrong_verdict_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["verdict"] = "ALLOW"
    with pytest.raises(ValueError, match="not a refusal-class verdict"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A8. does_not_execute False fails shape validation
# ---------------------------------------------------------------------------

def test_does_not_execute_false_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["does_not_execute"] = False
    with pytest.raises(ValueError, match="does_not_execute must be True"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A9. does_not_bind_consequence False fails shape validation
# ---------------------------------------------------------------------------

def test_does_not_bind_consequence_false_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["does_not_bind_consequence"] = False
    with pytest.raises(ValueError, match="does_not_bind_consequence must be True"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A10. Empty or None receipt_hash fails shape validation
# ---------------------------------------------------------------------------

def test_empty_receipt_hash_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["receipt_hash"] = ""
    with pytest.raises(ValueError, match="receipt_hash must be a non-empty string"):
        validate_refusal_receipt(projected)


def test_none_receipt_hash_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["receipt_hash"] = None
    with pytest.raises(ValueError):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# A11. prior_chain_state_hash carries prev_receipt_hash correctly
# ---------------------------------------------------------------------------

def test_prior_chain_state_hash_populated_for_sequence_gt_0():
    """A chained receipt (sequence > 0) carries prior_chain_state_hash."""
    first = _make_receipt(Verdict.DENY, sequence=0)
    second = _make_receipt(
        Verdict.HOLD,
        sequence=1,
        prev_receipt_hash=first.receipt_hash,
    )
    projected = to_refusal_receipt(second)
    assert projected["prior_chain_state_hash"] == first.receipt_hash
    assert validate_refusal_receipt(projected) is True


# ===========================================================================
# SECTION B — Hash consistency (verify_refusal_receipt_hash)
# These tests prove that receipt_hash reflects the canonical body.
# validate_refusal_receipt and verify_refusal_receipt_hash are separate:
#   validate_refusal_receipt — shape only
#   verify_refusal_receipt_hash — shape + hash consistency
# ===========================================================================

# ---------------------------------------------------------------------------
# B1. DENY projected receipt passes hash verification
# ---------------------------------------------------------------------------

def test_deny_passes_hash_verification():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    assert verify_refusal_receipt_hash(projected) is True


# ---------------------------------------------------------------------------
# B2. HOLD projected receipt passes hash verification
# ---------------------------------------------------------------------------

def test_hold_passes_hash_verification():
    receipt = _make_receipt(Verdict.HOLD)
    projected = to_refusal_receipt(receipt)
    assert verify_refusal_receipt_hash(projected) is True


# ---------------------------------------------------------------------------
# B3. REBIND_REQUIRED projected receipt passes hash verification
# ---------------------------------------------------------------------------

def test_rebind_required_passes_hash_verification():
    receipt = _make_receipt(Verdict.REBIND_REQUIRED)
    projected = to_refusal_receipt(receipt)
    assert verify_refusal_receipt_hash(projected) is True


# ---------------------------------------------------------------------------
# B4. Mutating reason_code after projection fails hash verification
#     (replaces former gap-documenting test)
# ---------------------------------------------------------------------------

def test_mutating_reason_code_fails_hash_consistency_check():
    """Mutating reason_code after projection fails hash verification.

    validate_refusal_receipt still passes (shape remains valid).
    verify_refusal_receipt_hash raises ValueError (hash is stale).
    """
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)

    projected["reason_code"] = "MUTATED_REASON_CODE"

    # Shape is still valid — shape validation cannot detect this
    assert validate_refusal_receipt(projected) is True

    # Hash consistency check catches the mutation
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_hash(projected)


# ---------------------------------------------------------------------------
# B5. Mutating proposed_action.object_id after projection fails hash verification
# ---------------------------------------------------------------------------

def test_mutating_proposed_action_fails_hash_consistency_check():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)

    projected["proposed_action"]["object_id"] = "MUTATED_OBJECT"

    # Shape is still valid
    assert validate_refusal_receipt(projected) is True

    # Hash consistency check catches the mutation
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_hash(projected)


# ---------------------------------------------------------------------------
# B6. Mutating verdict fails shape validation (caught before hash check)
# ---------------------------------------------------------------------------

def test_mutating_verdict_to_allow_fails_shape_before_hash_check():
    """Mutating verdict to ALLOW fails shape validation before hash check.

    verify_refusal_receipt_hash calls validate_refusal_receipt first,
    so an invalid verdict is caught at the shape layer.
    """
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)

    projected["verdict"] = "ALLOW"

    # Fails at shape validation (called inside verify_refusal_receipt_hash)
    with pytest.raises(ValueError, match="not a refusal-class verdict"):
        verify_refusal_receipt_hash(projected)


# ---------------------------------------------------------------------------
# B7. Empty receipt_hash fails shape validation inside hash verifier
# ---------------------------------------------------------------------------

def test_empty_receipt_hash_fails_inside_hash_verifier():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["receipt_hash"] = ""
    with pytest.raises(ValueError):
        verify_refusal_receipt_hash(projected)


# ---------------------------------------------------------------------------
# B8. Missing receipt_hash fails shape validation inside hash verifier
# ---------------------------------------------------------------------------

def test_missing_receipt_hash_fails_inside_hash_verifier():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    del projected["receipt_hash"]
    with pytest.raises(ValueError):
        verify_refusal_receipt_hash(projected)


# ---------------------------------------------------------------------------
# B9. Separation: validate_refusal_receipt and verify_refusal_receipt_hash
#     are distinct operations with distinct guarantees
# ---------------------------------------------------------------------------

def test_shape_and_hash_verification_are_separate_operations():
    """validate_refusal_receipt checks shape only.
    verify_refusal_receipt_hash checks shape + hash consistency.

    A receipt mutated in a body field passes shape validation but fails
    hash verification. These are provably different operations.
    """
    receipt = _make_receipt(Verdict.HOLD)
    projected = to_refusal_receipt(receipt)

    # Mutate a body field
    projected["reason"] = "This reason was changed after projection."

    # Shape check: passes (shape remains valid)
    assert validate_refusal_receipt(projected) is True

    # Hash check: fails (body no longer matches stored hash)
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_hash(projected)
