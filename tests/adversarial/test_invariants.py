"""Adversarial-vector tests, driven by INVARIANT_TEST_VECTORS_v1.json."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from receipt_chain_core import (
    Chain,
    ChainStatus,
    ChainedReceipt,
    Verdict,
    evaluate,
)


VECTORS_PATH = Path(__file__).resolve().parent / "INVARIANT_TEST_VECTORS_v1.json"
VECTORS = json.loads(VECTORS_PATH.read_text())["vectors"]
ISSUED = "2026-05-08T09:00:00Z"


def _by_id(vid: str):
    for v in VECTORS:
        if v["id"] == vid:
            return v
    raise KeyError(vid)


def test_v01_clean_chain():
    v = _by_id("V01_clean_chain_of_three_verifies_ok")
    chain = Chain()
    last = None
    for i, a in enumerate(v["actions"]):
        last, _ = evaluate(chain, proposed_action=a,
                           decision_id=f"d-{i}", issued_at=ISSUED)
    assert chain.verify().value == v["expected_chain_status"]
    assert last.verdict.value == v["expected_final_verdict"]


def test_v02_mutation_breaks_chain():
    v = _by_id("V02_mutation_breaks_chain")
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    target = chain.receipts[v["mutate_index"]]
    chain.receipts[v["mutate_index"]] = replace(
        target, **{v["mutate_field"]: v["mutate_value"]}
    )
    status = chain.verify().value
    assert status in v["expected_status_in"]


def test_v03_removal_breaks_chain():
    v = _by_id("V03_removal_breaks_chain")
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    del chain.receipts[v["remove_index"]]
    assert chain.verify().value == v["expected_status"]


def test_v04_reorder_breaks_chain():
    v = _by_id("V04_reorder_breaks_chain")
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    i, j = v["swap"]
    chain.receipts[i], chain.receipts[j] = chain.receipts[j], chain.receipts[i]
    assert chain.verify().value == v["expected_status"]


def test_v05_recent_refusal_changes_verdict():
    v = _by_id("V05_recent_refusal_changes_verdict")
    chain = Chain()
    seed = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-seed",
        proposed_action=v["seed_refusal_for"],
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(seed)
    r, _ = evaluate(chain, proposed_action=v["proposed_action"],
                    decision_id="d-test", issued_at=ISSUED)
    assert r.verdict.value == v["expected_verdict"]
    assert r.reason_code == v["expected_reason_code"]


def test_v06_unresolved_rebind_cycle():
    v = _by_id("V06_unresolved_rebind_blocks_then_clears")
    chain = Chain()
    blocked_seed = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="d-block",
        proposed_action=v["block_action"],
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded",
        reason="seeded",
        issued_at=ISSUED,
    )
    chain.append(blocked_seed)

    blocked, _ = evaluate(chain, proposed_action=v["block_action"],
                          decision_id="d-blocked-retry", issued_at=ISSUED)
    assert blocked.verdict.value == v["expected_blocked_verdict"]

    evaluate(chain,
             proposed_action={"action_type": "rebind", "object_id": v["object_id"]},
             decision_id="d-rebind", issued_at=ISSUED)
    cleared, _ = evaluate(chain, proposed_action=v["block_action"],
                          decision_id="d-cleared-retry", issued_at=ISSUED)
    assert cleared.verdict.value == v["expected_after_rebind_verdict"]


def test_v07_determinism():
    v = _by_id("V07_replay_is_deterministic")
    a, b = Chain(), Chain()
    for i, action in enumerate(v["actions"]):
        evaluate(a, proposed_action=action,
                 decision_id=f"d-{i}", issued_at=v["issued_at"])
        evaluate(b, proposed_action=action,
                 decision_id=f"d-{i}", issued_at=v["issued_at"])
    assert [r.receipt_hash for r in a.receipts] == [r.receipt_hash for r in b.receipts]
    for ra, rb in zip(a.receipts, b.receipts):
        assert ra.to_dict() == rb.to_dict()


def test_v08_boundary_declarations_present():
    v = _by_id("V08_boundary_declarations_present")
    chain = Chain()
    r, _ = evaluate(chain,
                    proposed_action={"action_type": "send_email", "object_id": "msg-0"},
                    decision_id="d", issued_at=ISSUED)
    body = r.to_dict()
    for key, expected in zip(v["expected_keys"], v["expected_values"]):
        assert body[key] == expected
