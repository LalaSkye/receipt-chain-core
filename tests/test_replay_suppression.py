"""Replay suppression tests — Issue #1.

Proves that replay_attempt_count is now decision-active in _decide().

Claim proven:
    replay_attempt_count participates in the demonstrated receipt-chain
    decision path.

Claim NOT proven:
    path-universal replay suppression, production readiness, payload
    binding, atomic commit, or full runtime governance.
"""

from __future__ import annotations

from receipt_chain_core import (
    Chain,
    ChainedReceipt,
    REFUSAL_WINDOW,
    Verdict,
    evaluate,
)
from receipt_chain_core.chain import REPLAY_SUPPRESS_THRESHOLD


ISSUED = "2026-05-08T09:00:00Z"
ACTION = {"action_type": "send_email", "object_id": "msg-001"}


def _append_allow(chain: Chain, action: dict, *, n: int, start_id: int = 0) -> None:
    """Append n ALLOW receipts for the given action."""
    for i in range(n):
        evaluate(
            chain,
            proposed_action=action,
            decision_id=f"d-allow-{start_id + i}",
            issued_at=ISSUED,
        )


def test_below_threshold_does_not_suppress():
    """replay_attempt_count below threshold: verdict is ALLOW."""
    chain = Chain()
    # Append REPLAY_SUPPRESS_THRESHOLD - 1 receipts for ACTION.
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD - 1)
    # The next evaluation is still below threshold.
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-below", issued_at=ISSUED)
    # At this point replay_attempt_count may equal threshold because the
    # window now includes all prior attempts. We verify the count
    # precisely: we appended THRESHOLD-1 receipts, so before this call
    # there are THRESHOLD-1 matching receipts in the window.
    # The count seen by _decide() for this call is THRESHOLD-1 < THRESHOLD.
    assert state.replay_attempt_count < REPLAY_SUPPRESS_THRESHOLD
    assert r.verdict == Verdict.ALLOW
    assert r.reason_code == "chain.clean_no_blocking_state"


def test_at_threshold_triggers_hold():
    """replay_attempt_count == REPLAY_SUPPRESS_THRESHOLD: HOLD."""
    chain = Chain()
    # Append exactly THRESHOLD receipts for ACTION so the window is full.
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD)
    # The next evaluation sees count == THRESHOLD.
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-at-threshold", issued_at=ISSUED)
    assert state.replay_attempt_count >= REPLAY_SUPPRESS_THRESHOLD
    assert r.verdict == Verdict.HOLD
    assert r.reason_code == "chain.replay_suppressed"


def test_above_threshold_still_hold():
    """replay_attempt_count > threshold: still HOLD."""
    chain = Chain()
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD + 1)
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-above", issued_at=ISSUED)
    assert r.verdict == Verdict.HOLD
    assert r.reason_code == "chain.replay_suppressed"


def test_replay_count_falls_out_of_window():
    """After enough unrelated receipts pad the window, replay count drops
    to zero and suppression lifts."""
    chain = Chain()
    # Seed THRESHOLD attempts so suppression would trigger.
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD)

    # Pad with REFUSAL_WINDOW unrelated receipts to push ACTION out.
    other = {"action_type": "publish_post", "object_id": "post-999"}
    for i in range(REFUSAL_WINDOW):
        evaluate(
            chain,
            proposed_action=other,
            decision_id=f"d-pad-{i}",
            issued_at=ISSUED,
        )

    # Now the window contains only unrelated receipts.
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-after-window", issued_at=ISSUED)
    assert state.replay_attempt_count == 0
    assert r.verdict == Verdict.ALLOW
    assert r.reason_code == "chain.clean_no_blocking_state"


def test_different_object_id_not_counted():
    """Attempts on a different object_id do not count toward suppression
    for the proposed action's object_id."""
    chain = Chain()
    other_action = {"action_type": "send_email", "object_id": "msg-OTHER"}
    _append_allow(chain, other_action, n=REPLAY_SUPPRESS_THRESHOLD)
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-diff-obj", issued_at=ISSUED)
    assert state.replay_attempt_count == 0
    assert r.verdict == Verdict.ALLOW


def test_rebind_action_type_not_counted():
    """rebind action type is not counted toward replay suppression for
    the target action type."""
    chain = Chain()
    rebind_action = {"action_type": "rebind", "object_id": ACTION["object_id"]}
    _append_allow(chain, rebind_action, n=REPLAY_SUPPRESS_THRESHOLD)
    r, state = evaluate(chain, proposed_action=ACTION,
                        decision_id="d-rebind-not-counted", issued_at=ISSUED)
    # rebind has different action_type so canonical hash differs; count must be 0
    assert state.replay_attempt_count == 0
    assert r.verdict == Verdict.ALLOW


def test_tamper_takes_priority_over_replay():
    """Tamper detection (row 1) fires before replay suppression (row 4)."""
    from dataclasses import replace

    chain = Chain()
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD)
    # Break the chain.
    chain.receipts[0] = replace(chain.receipts[0], reason="ALTERED")
    r, _ = evaluate(chain, proposed_action=ACTION,
                    decision_id="d-tamper-priority", issued_at=ISSUED)
    assert r.verdict == Verdict.HOLD
    assert r.reason_code == "chain.tamper_detected"


def test_recent_refusal_takes_priority_over_replay():
    """Recent refusal (row 3) fires before replay suppression (row 4)
    when both conditions are present."""
    chain = Chain()
    # Seed THRESHOLD ALLOW receipts so replay would suppress.
    _append_allow(chain, ACTION, n=REPLAY_SUPPRESS_THRESHOLD)
    # Now append a HOLD for the same action — this is a recent refusal.
    refusal = ChainedReceipt.build(
        sequence=len(chain.receipts),
        prev_receipt_hash=chain.head_hash,
        decision_id="d-refusal",
        proposed_action=ACTION,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(refusal)
    r, _ = evaluate(chain, proposed_action=ACTION,
                    decision_id="d-refusal-priority", issued_at=ISSUED)
    assert r.verdict == Verdict.HOLD
    # recent_refusal fires at row 3, before replay at row 4.
    assert r.reason_code == "chain.recent_refusal_in_window"
