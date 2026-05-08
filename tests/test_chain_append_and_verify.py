"""Append + verify tests for receipt-chain-core."""

from __future__ import annotations

import pytest

from receipt_chain_core import (
    Chain,
    ChainStatus,
    ChainedReceipt,
    Verdict,
    evaluate,
)


ISSUED = "2026-05-08T09:00:00Z"


def _send_action(i: int):
    return {"action_type": "send_email", "object_id": f"msg-{i}"}


def test_empty_chain_verifies_as_empty():
    chain = Chain()
    assert chain.verify() == ChainStatus.EMPTY
    assert chain.head_sequence is None
    assert chain.head_hash is None


def test_append_three_clean_receipts_verifies_ok():
    chain = Chain()
    for i in range(3):
        r, _ = evaluate(chain, proposed_action=_send_action(i),
                        decision_id=f"dec-{i:04d}", issued_at=ISSUED)
        assert r.verdict == Verdict.ALLOW
        assert r.sequence == i
    assert chain.verify() == ChainStatus.OK
    assert chain.head_sequence == 2
    assert chain.head_hash == chain.receipts[-1].receipt_hash


def test_sequence_is_strict_monotonic_from_zero():
    chain = Chain()
    for i in range(4):
        evaluate(chain, proposed_action=_send_action(i),
                 decision_id=f"d-{i}", issued_at=ISSUED)
    assert [r.sequence for r in chain.receipts] == [0, 1, 2, 3]


def test_prev_receipt_hash_links_correctly():
    chain = Chain()
    for i in range(3):
        evaluate(chain, proposed_action=_send_action(i),
                 decision_id=f"d-{i}", issued_at=ISSUED)
    rs = chain.receipts
    assert rs[0].prev_receipt_hash is None
    assert rs[1].prev_receipt_hash == rs[0].receipt_hash
    assert rs[2].prev_receipt_hash == rs[1].receipt_hash


def test_malformed_receipt_rejected():
    # missing object_id
    with pytest.raises(ValueError):
        ChainedReceipt.build(
            sequence=0,
            prev_receipt_hash=None,
            decision_id="d-x",
            proposed_action={"action_type": "send_email"},
            verdict=Verdict.ALLOW,
            reason_code="rc",
            reason="r",
            issued_at=ISSUED,
        )

    # negative sequence
    with pytest.raises(ValueError):
        ChainedReceipt.build(
            sequence=-1,
            prev_receipt_hash=None,
            decision_id="d-x",
            proposed_action={"action_type": "send_email", "object_id": "o"},
            verdict=Verdict.ALLOW,
            reason_code="rc",
            reason="r",
            issued_at=ISSUED,
        )

    # sequence 0 with non-null prev_receipt_hash
    with pytest.raises(ValueError):
        ChainedReceipt.build(
            sequence=0,
            prev_receipt_hash="deadbeef",
            decision_id="d-x",
            proposed_action={"action_type": "send_email", "object_id": "o"},
            verdict=Verdict.ALLOW,
            reason_code="rc",
            reason="r",
            issued_at=ISSUED,
        )


def test_replay_is_deterministic():
    """Same chain bytes + same proposed action + same issued_at + same
    decision_id -> identical receipt_hash."""
    a = Chain()
    b = Chain()
    for i in range(2):
        evaluate(a, proposed_action=_send_action(i),
                 decision_id=f"d-{i}", issued_at=ISSUED)
        evaluate(b, proposed_action=_send_action(i),
                 decision_id=f"d-{i}", issued_at=ISSUED)
    assert [r.receipt_hash for r in a.receipts] == [r.receipt_hash for r in b.receipts]


def test_boundary_declarations_present():
    chain = Chain()
    r, _ = evaluate(chain, proposed_action=_send_action(0),
                    decision_id="d-0", issued_at=ISSUED)
    body = r.to_dict()
    assert body["does_not_execute"] is True
    assert body["does_not_bind_consequence"] is True
