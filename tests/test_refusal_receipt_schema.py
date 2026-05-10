"""Tests for refusal receipt projection and validation.

Proves:
    receipt-chain-core can project a refusal-class ChainedReceipt into a
    typed refusal receipt shape and validate that shape on demonstrated paths.

Does not prove:
    Cryptographic signature, legal admissibility, production readiness,
    path-universal coverage, or full runtime governance fabric.

See also:
    Issue: Add optional signature verification for refusal receipts.
    Issue: Add refusal receipt hash-consistency verifier.
"""

from __future__ import annotations

import copy
import pytest

from receipt_chain_core.receipt import ChainedReceipt
from receipt_chain_core.verdict import Verdict
from receipt_chain_core.refusal_receipt import (
    REFUSAL_RECEIPT_SCHEMA_ID,
    to_refusal_receipt,
    validate_refusal_receipt,
)


# ---------------------------------------------------------------------------
# Shared fixtures
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


# ---------------------------------------------------------------------------
# 1. HOLD receipt produces valid refusal receipt
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
# 2. DENY receipt produces valid refusal receipt
# ---------------------------------------------------------------------------

def test_deny_produces_valid_refusal_receipt():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["verdict"] == "DENY"


# ---------------------------------------------------------------------------
# 3. REBIND_REQUIRED receipt produces valid refusal receipt
# ---------------------------------------------------------------------------

def test_rebind_required_produces_valid_refusal_receipt():
    receipt = _make_receipt(Verdict.REBIND_REQUIRED)
    projected = to_refusal_receipt(receipt)
    assert validate_refusal_receipt(projected) is True
    assert projected["verdict"] == "REBIND_REQUIRED"


# ---------------------------------------------------------------------------
# 4. ALLOW receipt cannot be projected as refusal receipt
# ---------------------------------------------------------------------------

def test_allow_cannot_be_projected_as_refusal_receipt():
    receipt = _make_receipt(Verdict.ALLOW)
    with pytest.raises(ValueError, match="cannot project ALLOW receipt"):
        to_refusal_receipt(receipt)


# ---------------------------------------------------------------------------
# 5. Missing required field fails validation
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
# 6. Wrong receipt_type fails validation
# ---------------------------------------------------------------------------

def test_wrong_receipt_type_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["receipt_type"] = "allow_receipt"
    with pytest.raises(ValueError, match="wrong receipt_type"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# 7. Wrong verdict fails validation
# ---------------------------------------------------------------------------

def test_wrong_verdict_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["verdict"] = "ALLOW"
    with pytest.raises(ValueError, match="not a refusal-class verdict"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# 8. does_not_execute False fails validation
# ---------------------------------------------------------------------------

def test_does_not_execute_false_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["does_not_execute"] = False
    with pytest.raises(ValueError, match="does_not_execute must be True"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# 9. does_not_bind_consequence False fails validation
# ---------------------------------------------------------------------------

def test_does_not_bind_consequence_false_fails_validation():
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    projected["does_not_bind_consequence"] = False
    with pytest.raises(ValueError, match="does_not_bind_consequence must be True"):
        validate_refusal_receipt(projected)


# ---------------------------------------------------------------------------
# 10. Fabricated receipt_hash missing or empty fails validation
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
# 11. Mutation note: hash-consistency verifier not yet implemented.
#     This test documents the open gap rather than pretending it is closed.
# ---------------------------------------------------------------------------

def test_mutating_reason_code_does_not_yet_trigger_hash_consistency_check():
    """Hash-consistency verification is not yet implemented.

    Mutating reason_code after projection produces a dict whose receipt_hash
    no longer matches the body, but validate_refusal_receipt does not yet
    detect this — it validates shape only, not hash consistency.

    This test documents the gap. See follow-up issue:
    'Add refusal receipt hash-consistency verifier.'
    """
    receipt = _make_receipt(Verdict.DENY)
    projected = to_refusal_receipt(receipt)
    original_hash = projected["receipt_hash"]

    # Mutate reason_code — hash is now stale
    projected["reason_code"] = "MUTATED_REASON_CODE"

    # Shape validation still passes — this is the known gap
    assert validate_refusal_receipt(projected) is True

    # The hash is unchanged (stale) — demonstrating the gap
    assert projected["receipt_hash"] == original_hash

    # NOTE: once 'Add refusal receipt hash-consistency verifier' is implemented,
    # this test should be updated to assert that validation raises ValueError.


# ---------------------------------------------------------------------------
# Bonus: prior_chain_state_hash carries prev_receipt_hash correctly
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
