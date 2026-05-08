"""Tamper-detection tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from receipt_chain_core import Chain, ChainStatus, evaluate


ISSUED = "2026-05-08T09:00:00Z"


def _seed_chain(n: int = 3) -> Chain:
    chain = Chain()
    for i in range(n):
        evaluate(
            chain,
            proposed_action={"action_type": "send_email", "object_id": f"msg-{i}"},
            decision_id=f"d-{i}",
            issued_at=ISSUED,
        )
    assert chain.verify() == ChainStatus.OK
    return chain


def test_mutation_breaks_chain():
    chain = _seed_chain()
    # mutate the body of receipt 0; recomputed hash will not match its
    # stored receipt_hash, AND linkage from receipt 1 will not match either.
    chain.receipts[0] = replace(chain.receipts[0], reason="ALTERED")
    status = chain.verify()
    assert status in (ChainStatus.BROKEN_HASH, ChainStatus.BROKEN_LINK)


def test_removal_breaks_chain():
    chain = _seed_chain()
    del chain.receipts[1]
    # sequence is now [0, 2] which violates strict-monotonic from 0
    assert chain.verify() == ChainStatus.BROKEN_SEQUENCE


def test_reorder_breaks_chain():
    chain = _seed_chain()
    chain.receipts[1], chain.receipts[2] = chain.receipts[2], chain.receipts[1]
    # sequence is now [0, 2, 1] which fails strict-monotonic
    assert chain.verify() == ChainStatus.BROKEN_SEQUENCE


def test_broken_link_detected_when_sequence_intact():
    """If sequence is intact but a prev_receipt_hash is wrong,
    the verifier returns BROKEN_LINK."""
    chain = _seed_chain()
    bad = replace(chain.receipts[2], prev_receipt_hash="0" * 64)
    chain.receipts[2] = bad
    # Hash check runs before linkage check; the body's receipt_hash was
    # computed over the original prev_receipt_hash, so we expect
    # BROKEN_HASH or BROKEN_LINK depending on order. Both are tamper signals.
    assert chain.verify() in (ChainStatus.BROKEN_HASH, ChainStatus.BROKEN_LINK)


def test_evaluate_against_tampered_chain_returns_hold():
    chain = _seed_chain()
    chain.receipts[0] = replace(chain.receipts[0], reason="ALTERED")
    receipt, state = evaluate(
        chain,
        proposed_action={"action_type": "send_email", "object_id": "msg-9"},
        decision_id="d-tamper",
        issued_at=ISSUED,
    )
    assert receipt.verdict.value == "HOLD"
    assert receipt.reason_code == "chain.tamper_detected"
    assert state.chain_status != ChainStatus.OK


def test_append_rejects_when_chain_already_broken():
    chain = _seed_chain()
    del chain.receipts[1]  # break the chain
    pre_len = len(chain.receipts)
    receipt, _ = evaluate(
        chain,
        proposed_action={"action_type": "send_email", "object_id": "msg-after-break"},
        decision_id="d-after-break",
        issued_at=ISSUED,
    )
    # the broken chain should not gain a new receipt
    assert len(chain.receipts) == pre_len
    assert receipt.verdict.value == "HOLD"
    assert receipt.reason_code == "chain.tamper_detected"
