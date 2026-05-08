"""Projector tests."""

from __future__ import annotations

from receipt_chain_core import (
    Chain,
    ChainStatus,
    ChainedReceipt,
    REFUSAL_WINDOW,
    Verdict,
    evaluate,
    project,
)


ISSUED = "2026-05-08T09:00:00Z"
SCHEMA = "receipt_chain_core.projector.v0.1"


def _seed_refusal(chain: Chain, action: dict, *, sequence: int = 0) -> ChainedReceipt:
    r = ChainedReceipt.build(
        sequence=sequence,
        prev_receipt_hash=(chain.head_hash if sequence > 0 else None),
        decision_id=f"d-prior-{sequence}",
        proposed_action=action,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded refusal",
        issued_at=ISSUED,
    )
    chain.append(r)
    return r


def test_projector_schema_recorded():
    chain = Chain()
    state = project(chain.receipts, {"action_type": "x", "object_id": "y"}, ChainStatus.EMPTY)
    assert state.schema == SCHEMA

    r, _ = evaluate(chain, proposed_action={"action_type": "x", "object_id": "y"},
                    decision_id="d", issued_at=ISSUED)
    assert r.projector_schema == SCHEMA
    assert r.to_dict()["projector_schema"] == SCHEMA


def test_empty_chain_projection():
    chain = Chain()
    state = project(chain.receipts, {"action_type": "x", "object_id": "y"}, ChainStatus.EMPTY)
    assert state.chain_status == ChainStatus.EMPTY
    assert state.head_sequence is None
    assert state.recent_refusal is None
    assert state.unresolved_rebind is False
    assert state.replay_attempt_count == 0


def test_projector_surfaces_recent_refusal():
    chain = Chain()
    action = {"action_type": "send_email", "object_id": "msg-1"}
    _seed_refusal(chain, action, sequence=0)
    state = project(chain.receipts, action, chain.verify())
    assert state.recent_refusal is not None
    assert state.recent_refusal["verdict"] == "HOLD"
    assert state.recent_refusal["sequence"] == 0


def test_projector_does_not_surface_unrelated_refusal():
    chain = Chain()
    other = {"action_type": "publish_post", "object_id": "post-9"}
    _seed_refusal(chain, other, sequence=0)
    state = project(chain.receipts,
                    {"action_type": "send_email", "object_id": "msg-1"},
                    chain.verify())
    assert state.recent_refusal is None


def test_refusal_window_drops_old_refusals():
    """Pad enough ALLOW receipts after a refusal so the refusal falls out
    of the window of size REFUSAL_WINDOW."""
    chain = Chain()
    target = {"action_type": "send_email", "object_id": "msg-1"}
    _seed_refusal(chain, target, sequence=0)

    # pad with REFUSAL_WINDOW unrelated ALLOWs to push the refusal out
    for i in range(REFUSAL_WINDOW):
        evaluate(chain,
                 proposed_action={"action_type": "publish_post", "object_id": f"post-{i}"},
                 decision_id=f"d-pad-{i}", issued_at=ISSUED)

    state = project(chain.receipts, target, chain.verify())
    # only the last REFUSAL_WINDOW receipts are inspected; the refusal
    # at sequence 0 is now out of window
    assert state.recent_refusal is None


def test_unresolved_rebind_detected():
    chain = Chain()
    blocked = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked)
    state = project(chain.receipts,
                    {"action_type": "send_email", "object_id": "obj-X"},
                    chain.verify())
    assert state.unresolved_rebind is True


def test_rebind_clears_unresolved_for_same_object():
    chain = Chain()
    blocked = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked)

    # successful rebind
    evaluate(chain,
             proposed_action={"action_type": "rebind", "object_id": "obj-X"},
             decision_id="d-rebind", issued_at=ISSUED)

    state = project(chain.receipts,
                    {"action_type": "send_email", "object_id": "obj-X"},
                    chain.verify())
    assert state.unresolved_rebind is False


def test_unresolved_rebind_object_scoped():
    """An unresolved rebind on obj-X must not block actions on obj-Y."""
    chain = Chain()
    blocked = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked)
    state = project(chain.receipts,
                    {"action_type": "send_email", "object_id": "obj-Y"},
                    chain.verify())
    assert state.unresolved_rebind is False
