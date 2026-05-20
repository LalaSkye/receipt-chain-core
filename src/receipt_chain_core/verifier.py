"""Standalone refusal receipt verifier.

Schema id: receipt_chain_core.refusal_receipt.v0.1

Provides:
    verify_refusal_receipt_artifact — verify a refusal receipt artefact for
        shape, hash consistency, optional Ed25519 signature, and optional
        expected prior-chain-state linkage.

Verification order (PRIMARY DESIGN RULE — shape first, hash next):
    1. shape check          (always)
    2. hash recompute       (always)
    3. signature check      (only if public_key is supplied)
    4. chain-state linkage  (only if expected_prior_chain_state_hash is supplied)
    5. return True          (only if all requested checks pass)
    6. raise ValueError     (on any failed check)

Calling this function proves:
    A refusal receipt artefact produced by receipt-chain-core has a valid
    shape, an internally consistent receipt_hash, and (when requested) a
    valid Ed25519 signature and/or an expected prior-chain-state linkage,
    on demonstrated paths.

Does not prove:
    Legal identity, human authority, institutional authority, legal
    admissibility, production security, compliance, adoption, field standard,
    full runtime governance fabric, full replay, full chain reconstruction,
    standing composition, or path-universal coverage.

This module delegates all checks to the existing primitive functions:
    validate_refusal_receipt        — shape check
    verify_refusal_receipt_hash     — shape + hash consistency
    verify_refusal_receipt_signature — shape + hash + Ed25519 signature

It does not duplicate their internals.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .refusal_receipt import (
    validate_refusal_receipt,
    verify_refusal_receipt_hash,
    verify_refusal_receipt_signature,
)


def verify_refusal_receipt_artifact(
    receipt: Mapping[str, Any],
    *,
    public_key: Optional[Any] = None,
    expected_prior_chain_state_hash: Optional[str] = None,
) -> bool:
    """Verify a refusal receipt artefact.

    Executes checks in the order defined by the PRIMARY DESIGN RULE:

        1. Shape check (always).
           Delegates to validate_refusal_receipt(receipt).
           Raises ValueError on any structural violation.

        2. Hash recompute (always).
           Delegates to verify_refusal_receipt_hash(receipt).
           Raises ValueError if receipt_hash does not match the canonical body.
           Detects post-projection mutation of any body field.

        3. Signature check (only if public_key is supplied).
           Delegates to verify_refusal_receipt_signature(receipt, public_key).
           Raises ValueError if the signature is missing, malformed, or invalid
           for the supplied public key.

        4. Prior-chain-state linkage check
           (only if expected_prior_chain_state_hash is supplied).
           Checks:
               receipt["prior_chain_state_hash"] == expected_prior_chain_state_hash
           This is the seed condition only — not full chain reconstruction.
           Raises ValueError if the values do not match.

        5. Returns True only if all requested checks pass.

    Args:
        receipt:
            A refusal receipt dict (Mapping) as produced by to_refusal_receipt().
            Must not be mutated between projection and verification.
        public_key:
            Optional Ed25519PublicKey instance (from the cryptography library).
            If supplied, step 3 runs. If None, step 3 is skipped.
        expected_prior_chain_state_hash:
            Optional str. If supplied, step 4 runs and checks that
            receipt["prior_chain_state_hash"] equals this value.
            If None, step 4 is skipped — no linkage check is performed.

    Returns:
        True if all requested checks pass.

    Raises:
        ValueError on any failed check, with a message identifying the step
        and the nature of the failure.
    """
    # Step 1 + 2: shape and hash (always; verify_refusal_receipt_hash calls
    # validate_refusal_receipt internally, so one call covers both).
    verify_refusal_receipt_hash(receipt)

    # Step 3: optional signature check.
    if public_key is not None:
        verify_refusal_receipt_signature(receipt, public_key)

    # Step 4: optional prior-chain-state linkage check (seed condition).
    if expected_prior_chain_state_hash is not None:
        actual = receipt.get("prior_chain_state_hash")
        if actual != expected_prior_chain_state_hash:
            raise ValueError(
                f"prior_chain_state_hash mismatch: "
                f"expected {expected_prior_chain_state_hash!r}, "
                f"got {actual!r}. "
                "The receipt does not link to the expected prior chain state."
            )

    return True
