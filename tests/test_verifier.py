"""Tests for verify_refusal_receipt_artifact (Issue #14).

Proves:
    receipt-chain-core can verify a produced refusal receipt artefact for
    shape, hash consistency, optional Ed25519 signature validity, and optional
    expected prior-chain-state linkage on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal
    admissibility, production security, compliance, adoption, field standard,
    full runtime governance fabric, full replay, full chain reconstruction,
    standing composition, or path-universal coverage.

Test index:
    T1  unsigned valid receipt passes shape + hash
    T2  signed valid receipt passes shape + hash + signature
    T3  tampered reason_code fails
    T4  tampered proposed_action.object_id fails
    T5  attacker recomputes receipt_hash after mutation but signature still fails
    T6  wrong public key fails
    T7  expected prior-chain-state hash match passes
    T8  expected prior-chain-state hash mismatch fails
    T9  missing expected prior-chain-state hash skips linkage check
    T10 verifier does not mutate the receipt dict
    T11 (optional) invalid mapping type fails
    T12 (optional) malformed signature fails through existing signature verifier
    T13 (optional) unknown extra field fails through existing shape validator
"""

from __future__ import annotations

import copy

import pytest

from receipt_chain_core.receipt import ChainedReceipt
from receipt_chain_core.refusal_receipt import (
    sign_refusal_receipt,
    to_refusal_receipt,
)
from receipt_chain_core.verdict import Verdict
from receipt_chain_core.verifier import verify_refusal_receipt_artifact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chained_receipt(
    verdict: Verdict = Verdict.DENY,
    sequence: int = 0,
    prev_receipt_hash: str | None = None,
) -> ChainedReceipt:
    return ChainedReceipt.build(
        sequence=sequence,
        prev_receipt_hash=prev_receipt_hash,
        decision_id=f"verifier-test-{verdict.value.lower()}",
        proposed_action={"action_type": "write", "object_id": "obj-verifier-001"},
        verdict=verdict,
        reason_code="TEST_VERIFIER_REASON",
        reason="Test reason for verifier test.",
        issued_at="2026-05-10T11:00:00Z",
    )


def _make_unsigned_receipt(verdict: Verdict = Verdict.DENY) -> dict:
    return to_refusal_receipt(_make_chained_receipt(verdict))


def _make_ed25519_keypair():
    """Return (private_key, public_key) Ed25519 pair via cryptography library."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


# ---------------------------------------------------------------------------
# T1 — unsigned valid receipt passes shape + hash
# ---------------------------------------------------------------------------

def test_t1_unsigned_valid_receipt_passes_shape_and_hash():
    """An unsigned valid receipt produced by to_refusal_receipt passes
    shape and hash checks. No public_key supplied — signature step skipped.
    No expected_prior_chain_state_hash supplied — linkage step skipped.
    """
    receipt = _make_unsigned_receipt()
    assert verify_refusal_receipt_artifact(receipt) is True


# ---------------------------------------------------------------------------
# T2 — signed valid receipt passes shape + hash + signature
# ---------------------------------------------------------------------------

def test_t2_signed_valid_receipt_passes_all_three_checks():
    """A signed valid receipt passes shape, hash, and signature checks
    when the matching public key is supplied.
    """
    private_key, public_key = _make_ed25519_keypair()
    unsigned = _make_unsigned_receipt()
    signed = sign_refusal_receipt(unsigned, private_key)
    assert verify_refusal_receipt_artifact(signed, public_key=public_key) is True


# ---------------------------------------------------------------------------
# T3 — tampered reason_code fails
# ---------------------------------------------------------------------------

def test_t3_tampered_reason_code_fails():
    """Mutating reason_code after projection invalidates receipt_hash.
    The verifier raises ValueError at the hash check step.
    """
    receipt = _make_unsigned_receipt()
    receipt["reason_code"] = "TAMPERED_REASON"
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_artifact(receipt)


# ---------------------------------------------------------------------------
# T4 — tampered proposed_action.object_id fails
# ---------------------------------------------------------------------------

def test_t4_tampered_proposed_action_object_id_fails():
    """Mutating proposed_action.object_id after projection invalidates
    receipt_hash. The verifier raises ValueError at the hash check step.
    """
    receipt = _make_unsigned_receipt()
    receipt["proposed_action"]["object_id"] = "TAMPERED_OBJECT"
    with pytest.raises(ValueError, match="receipt_hash mismatch"):
        verify_refusal_receipt_artifact(receipt)


# ---------------------------------------------------------------------------
# T5 — attacker recomputes receipt_hash after mutation but signature fails
# ---------------------------------------------------------------------------

def test_t5_attacker_recomputes_hash_but_signature_still_fails():
    """An attacker who mutates a body field and recomputes receipt_hash to
    match passes the hash check but fails signature verification, because
    the signature was computed over the original canonical body.

    This proves that signature verification provides a stronger guarantee
    than hash verification alone when a public key is available.
    """
    from receipt_chain_core.hashing import sha256_hex
    from receipt_chain_core.refusal_receipt import (
        REFUSAL_RECEIPT_SCHEMA_ID,
        _BODY_FIELDS,  # noqa: PLC2701 — test needs canonical body field list
    )

    private_key, public_key = _make_ed25519_keypair()
    unsigned = _make_unsigned_receipt()
    signed = sign_refusal_receipt(unsigned, private_key)

    # Attacker mutates reason_code
    signed["reason_code"] = "ATTACKER_REASON"

    # Attacker recomputes receipt_hash so the hash check would pass
    body = {k: signed[k] for k in _BODY_FIELDS}
    signed["receipt_hash"] = sha256_hex(body)

    # Hash check alone would now pass — but the signature was over the original
    # body, so signature verification catches the mutation.
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_refusal_receipt_artifact(signed, public_key=public_key)


# ---------------------------------------------------------------------------
# T6 — wrong public key fails
# ---------------------------------------------------------------------------

def test_t6_wrong_public_key_fails():
    """A receipt signed with key A fails verification when key B is supplied."""
    private_key_a, _ = _make_ed25519_keypair()
    _, public_key_b = _make_ed25519_keypair()

    unsigned = _make_unsigned_receipt()
    signed = sign_refusal_receipt(unsigned, private_key_a)

    with pytest.raises(ValueError, match="signature verification failed"):
        verify_refusal_receipt_artifact(signed, public_key=public_key_b)


# ---------------------------------------------------------------------------
# T7 — expected prior-chain-state hash match passes
# ---------------------------------------------------------------------------

def test_t7_expected_prior_chain_state_hash_match_passes():
    """When expected_prior_chain_state_hash matches the receipt field,
    the linkage check passes and the verifier returns True.
    """
    first = _make_chained_receipt(Verdict.DENY, sequence=0)
    second_chain = _make_chained_receipt(
        Verdict.HOLD, sequence=1, prev_receipt_hash=first.receipt_hash
    )
    second_receipt = to_refusal_receipt(second_chain)

    assert verify_refusal_receipt_artifact(
        second_receipt,
        expected_prior_chain_state_hash=first.receipt_hash,
    ) is True


# ---------------------------------------------------------------------------
# T8 — expected prior-chain-state hash mismatch fails
# ---------------------------------------------------------------------------

def test_t8_expected_prior_chain_state_hash_mismatch_fails():
    """When expected_prior_chain_state_hash does not match the receipt field,
    the verifier raises ValueError naming the mismatch.
    """
    receipt = _make_unsigned_receipt()  # sequence=0, prior_chain_state_hash=None
    wrong_hash = "a" * 64  # plausible-looking hash that does not match

    with pytest.raises(ValueError, match="prior_chain_state_hash mismatch"):
        verify_refusal_receipt_artifact(
            receipt,
            expected_prior_chain_state_hash=wrong_hash,
        )


# ---------------------------------------------------------------------------
# T9 — missing expected prior-chain-state hash skips linkage check
# ---------------------------------------------------------------------------

def test_t9_no_expected_hash_skips_linkage_check():
    """When expected_prior_chain_state_hash is not supplied (None),
    the linkage check step is skipped entirely.
    A receipt with prior_chain_state_hash=None passes without error.
    """
    receipt = _make_unsigned_receipt()  # sequence=0, prior_chain_state_hash=None
    # No expected hash supplied — linkage step must not run
    assert verify_refusal_receipt_artifact(receipt) is True


# ---------------------------------------------------------------------------
# T10 — verifier does not mutate the receipt dict
# ---------------------------------------------------------------------------

def test_t10_verifier_does_not_mutate_receipt():
    """verify_refusal_receipt_artifact must not mutate the input dict.
    The dict before and after the call must be equal in all fields.
    """
    receipt = _make_unsigned_receipt()
    snapshot = copy.deepcopy(receipt)

    verify_refusal_receipt_artifact(receipt)

    assert receipt == snapshot, (
        "verifier mutated the receipt dict: "
        f"before={snapshot!r}, after={receipt!r}"
    )


# ===========================================================================
# Optional tests (cheap — all delegate to existing validators)
# ===========================================================================

# ---------------------------------------------------------------------------
# T11 — invalid mapping type fails through existing shape validator
# ---------------------------------------------------------------------------

def test_t11_invalid_mapping_type_fails():
    """A non-Mapping input raises ValueError at the shape check step."""
    with pytest.raises(ValueError, match="must be a mapping"):
        verify_refusal_receipt_artifact(["not", "a", "mapping"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T12 — malformed signature fails through existing signature verifier
# ---------------------------------------------------------------------------

def test_t12_malformed_signature_fails():
    """A receipt with a malformed base64url signature raises ValueError
    at the signature verification step.
    """
    private_key, public_key = _make_ed25519_keypair()
    unsigned = _make_unsigned_receipt()
    signed = sign_refusal_receipt(unsigned, private_key)

    # Replace signature with invalid base64url content
    signed["signature"] = "!!!not-valid-base64!!!"

    with pytest.raises(ValueError):
        verify_refusal_receipt_artifact(signed, public_key=public_key)


# ---------------------------------------------------------------------------
# T13 — unknown extra field fails through existing shape validator
# ---------------------------------------------------------------------------

def test_t13_unknown_extra_field_fails():
    """A receipt with an unknown extra field raises ValueError
    at the shape check step (fail-closed on unknown fields).
    """
    receipt = _make_unsigned_receipt()
    receipt["unexpected_field"] = "unexpected_value"

    with pytest.raises(ValueError, match="unexpected fields"):
        verify_refusal_receipt_artifact(receipt)
