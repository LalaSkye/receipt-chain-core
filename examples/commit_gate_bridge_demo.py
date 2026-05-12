#!/usr/bin/env python3
"""commit_gate_bridge_demo.py — receipt-chain → commit-gate reachability demo.

This demo shows one narrow bridge condition:

    receipt-chain verdict decides whether a commit boundary is reached.

It does not import commit-gate-core. The local adapter deliberately exposes only
three fields a downstream commit gate would make visible on this path:

    commit_gate_reached
    commit_gate_code
    mutation_performed

Claim boundary:
    - Demonstrates bridge reachability on the shown path.
    - Does not prove production integration.
    - Does not prove path-universal routing.
    - Does not execute external side effects.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import Chain, ChainedReceipt, Verdict, evaluate  # noqa: E402


ISSUED = "2026-05-12T08:15:00Z"
ACTION = {"action_type": "send_email", "object_id": "msg-bridge"}


@dataclass(frozen=True)
class BridgeResult:
    """Visible bridge outcome for one proposed action."""

    scenario: str
    receipt_chain_verdict: str
    receipt_chain_reason_code: str
    commit_gate_reached: bool
    commit_gate_code: Optional[str]
    mutation_performed: bool


class DemoCommitGateAdapter:
    """Small local adapter for bridge visibility.

    This is not commit-gate-core. It is the thinnest local stand-in needed to
    show reachability and mutation truth values inside this repo.
    """

    def __init__(self) -> None:
        self.mutations: list[Mapping[str, str]] = []

    def execute(self, *, decision_record: Optional[Mapping[str, str]], proposed_action: Mapping[str, str]) -> tuple[str, bool]:
        if decision_record is None:
            return "DENY:NO_DECISION_RECORD", False

        required = {
            "verdict": "ALLOW",
            "action_type": proposed_action["action_type"],
            "object_id": proposed_action["object_id"],
        }
        for field, expected in required.items():
            if decision_record.get(field) != expected:
                return f"DENY:SCOPE_OR_VERDICT_MISMATCH:{field}", False

        self.mutations.append(dict(proposed_action))
        return "ALLOW", True


def bridge_evaluate(
    *,
    scenario: str,
    chain: Chain,
    proposed_action: Mapping[str, str],
    decision_id: str,
    decision_record: Optional[Mapping[str, str]],
) -> BridgeResult:
    """Evaluate receipt-chain state before the commit adapter is reached."""

    receipt, _state = evaluate(
        chain,
        proposed_action=proposed_action,
        decision_id=decision_id,
        issued_at=ISSUED,
    )

    if receipt.verdict != Verdict.ALLOW:
        return BridgeResult(
            scenario=scenario,
            receipt_chain_verdict=receipt.verdict.value,
            receipt_chain_reason_code=receipt.reason_code,
            commit_gate_reached=False,
            commit_gate_code=None,
            mutation_performed=False,
        )

    gate = DemoCommitGateAdapter()
    gate_code, mutation_performed = gate.execute(
        decision_record=decision_record,
        proposed_action=proposed_action,
    )

    return BridgeResult(
        scenario=scenario,
        receipt_chain_verdict=receipt.verdict.value,
        receipt_chain_reason_code=receipt.reason_code,
        commit_gate_reached=True,
        commit_gate_code=gate_code,
        mutation_performed=mutation_performed,
    )


def _seed_recent_refusal(chain: Chain) -> None:
    prior = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="bridge-prior-refusal",
        proposed_action=ACTION,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded prior refusal for bridge demo",
        issued_at=ISSUED,
    )
    status = chain.append(prior)
    if status.value != "OK":
        raise AssertionError(f"failed to seed prior refusal: {status.value}")


def scenario_chain_blocks_before_commit_gate() -> BridgeResult:
    chain = Chain()
    _seed_recent_refusal(chain)
    return bridge_evaluate(
        scenario="chain blocks before commit gate",
        chain=chain,
        proposed_action=ACTION,
        decision_id="bridge-s1",
        decision_record={"verdict": "ALLOW", "action_type": "send_email", "object_id": "msg-bridge"},
    )


def scenario_clean_chain_missing_authority() -> BridgeResult:
    chain = Chain()
    return bridge_evaluate(
        scenario="clean chain, missing authority",
        chain=chain,
        proposed_action=ACTION,
        decision_id="bridge-s2",
        decision_record=None,
    )


def scenario_clean_chain_valid_authority() -> BridgeResult:
    chain = Chain()
    return bridge_evaluate(
        scenario="clean chain, valid authority",
        chain=chain,
        proposed_action=ACTION,
        decision_id="bridge-s3",
        decision_record={"verdict": "ALLOW", "action_type": "send_email", "object_id": "msg-bridge"},
    )


def _print_result(index: int, result: BridgeResult) -> None:
    reached = str(result.commit_gate_reached).lower()
    mutated = str(result.mutation_performed).lower()
    gate_code = result.commit_gate_code or "NOT_REACHED"
    print(
        f"[{index}/3] {result.scenario:<36} "
        f"chain={result.receipt_chain_verdict:<16} "
        f"gate_reached={reached:<5} "
        f"gate={gate_code:<25} "
        f"mutation={mutated}"
    )


def main() -> int:
    print("=" * 96)
    print("  receipt-chain-core — commit gate bridge demo")
    print("  claim: receipt-chain verdict decides whether commit boundary is reached")
    print("=" * 96)
    print()

    results = [
        scenario_chain_blocks_before_commit_gate(),
        scenario_clean_chain_missing_authority(),
        scenario_clean_chain_valid_authority(),
    ]

    expected = [
        ("HOLD", False, None, False),
        ("ALLOW", True, "DENY:NO_DECISION_RECORD", False),
        ("ALLOW", True, "ALLOW", True),
    ]

    all_match = True
    for index, (result, expected_tuple) in enumerate(zip(results, expected), start=1):
        _print_result(index, result)
        actual = (
            result.receipt_chain_verdict,
            result.commit_gate_reached,
            result.commit_gate_code,
            result.mutation_performed,
        )
        if actual != expected_tuple:
            all_match = False
            print(f"      expected={expected_tuple!r}")
            print(f"      actual  ={actual!r}")

    print()
    if all_match:
        print("ALL BRIDGE SCENARIOS PRODUCED EXPECTED RESULTS")
        return 0

    print("BRIDGE DEMO MISMATCH — at least one scenario diverged from expectation")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
