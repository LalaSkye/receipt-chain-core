"""Verdict-changes-under-chain-state tests.

These prove the core claim: prior chain state participates in the next
admissibility decision. Same proposed action + different chain state →
different verdict.
"""

from __future__ import annotations

from receipt_chain_core import (
    Chain,
    ChainedReceipt,
    Verdict,
    evaluate,
)


ISSUED = "2026-05-08T09:00:00Z"
ACTION = {"action_type": "send_email", "object_id": "msg-001"}


def test_clean_chain_allows():
    chain = Chain()
    r, _ = evaluate(chain, proposed_action=ACTION,
                    decision_id="d-clean", issued_at=ISSUED)
    assert r.verdict == Verdict.ALLOW
    assert r.reason_code == "chain.clean_no_blocking_state"


def test_recent_refusal_changes_to_hold():
    chain = Chain()
    seed = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-prior-refusal",
        proposed_action=ACTION,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded refusal",
        issued_at=ISSUED,
    )
    chain.append(seed)
    r, _ = evaluate(chain, proposed_action=ACTION,
                    decision_id="d-after-refusal", issued_at=ISSUED)
    assert r.verdict == Verdict.HOLD
    assert r.reason_code == "chain.recent_refusal_in_window"


def test_unresolved_rebind_changes_to_rebind_required():
    chain = Chain()
    blocked = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action=ACTION,
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked)
    r, _ = evaluate(chain, proposed_action=ACTION,
                    decision_id="d-blocked-retry", issued_at=ISSUED)
    assert r.verdict == Verdict.REBIND_REQUIRED
    assert r.reason_code == "chain.unresolved_rebind"


def test_rebind_then_retry_returns_allow():
    chain = Chain()
    blocked = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action=ACTION,
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked)

    rebind, _ = evaluate(
        chain,
        proposed_action={"action_type": "rebind", "object_id": ACTION["object_id"]},
        decision_id="d-rebind",
        issued_at=ISSUED,
    )
    assert rebind.verdict == Verdict.ALLOW

    retry, _ = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-retry", issued_at=ISSUED)
    assert retry.verdict == Verdict.ALLOW


def test_two_chains_differ_only_by_recent_refusal():
    """Same proposed action; only difference between chains is one
    refusal in chain B. Verdicts must differ."""
    a = Chain()
    b = Chain()

    refusal = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-refusal-b",
        proposed_action=ACTION,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded",
        issued_at=ISSUED,
    )
    b.append(refusal)

    ra, _ = evaluate(a, proposed_action=ACTION, decision_id="d-a", issued_at=ISSUED)
    rb, _ = evaluate(b, proposed_action=ACTION, decision_id="d-b", issued_at=ISSUED)

    assert ra.verdict == Verdict.ALLOW
    assert rb.verdict == Verdict.HOLD
    assert ra.verdict != rb.verdict
