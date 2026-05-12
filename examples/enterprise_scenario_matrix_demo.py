#!/usr/bin/env python3
"""enterprise_scenario_matrix_demo.py — enterprise-shaped bridge matrix.

This demo widens the bridge shape without widening the claim.

It demonstrates the same bounded pattern across three enterprise-shaped
consequence classes:

    prior receipt state
    → receipt-chain verdict
    → commit boundary reached or not reached
    → mutation true or false

Claim boundary:
    - Demonstrates local, in-memory scenario paths only.
    - Does not prove production deployment.
    - Does not prove enterprise adoption.
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


ISSUED = "2026-05-12T08:45:00Z"

SCENARIOS = [
    {
        "label": "external communication",
        "action_type": "send_email",
        "object_id": "email-001",
    },
    {
        "label": "access control",
        "action_type": "grant_access",
        "object_id": "user-privilege-001",
    },
    {
        "label": "financial operation",
        "action_type": "approve_payment",
        "object_id": "payment-001",
    },
]


@dataclass(frozen=True)
class MatrixResult:
    label: str
    path: str
    action_type: str
    object_id: str
    receipt_chain_verdict: str
    receipt_chain_reason_code: str
    commit_gate_reached: bool
    commit_gate_code: Optional[str]
    mutation_performed: bool


class DemoCommitGateAdapter:
    """Local commit-boundary adapter for matrix visibility.

    This adapter is intentionally tiny. It does not claim to be production
    commit-gate-core. It only exposes whether the commit boundary was reached
    and whether the local demo mutation occurred.
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


def _action(spec: Mapping[str, str]) -> dict[str, str]:
    return {
        "action_type": spec["action_type"],
        "object_id": spec["object_id"],
    }


def _valid_authority_for(action: Mapping[str, str]) -> dict[str, str]:
    return {
        "verdict": "ALLOW",
        "action_type": action["action_type"],
        "object_id": action["object_id"],
    }


def _seed_prior_refusal(chain: Chain, action: Mapping[str, str]) -> None:
    prior = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id=f"matrix-prior-refusal-{action['action_type']}",
        proposed_action=action,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded prior refusal for enterprise matrix demo",
        issued_at=ISSUED,
    )
    status = chain.append(prior)
    if status.value != "OK":
        raise AssertionError(f"failed to seed prior refusal: {status.value}")


def _bridge_evaluate(
    *,
    label: str,
    path: str,
    chain: Chain,
    action: Mapping[str, str],
    decision_id: str,
    decision_record: Optional[Mapping[str, str]],
) -> MatrixResult:
    receipt, _state = evaluate(
        chain,
        proposed_action=action,
        decision_id=decision_id,
        issued_at=ISSUED,
    )

    if receipt.verdict != Verdict.ALLOW:
        return MatrixResult(
            label=label,
            path=path,
            action_type=action["action_type"],
            object_id=action["object_id"],
            receipt_chain_verdict=receipt.verdict.value,
            receipt_chain_reason_code=receipt.reason_code,
            commit_gate_reached=False,
            commit_gate_code=None,
            mutation_performed=False,
        )

    gate = DemoCommitGateAdapter()
    gate_code, mutation_performed = gate.execute(
        decision_record=decision_record,
        proposed_action=action,
    )

    return MatrixResult(
        label=label,
        path=path,
        action_type=action["action_type"],
        object_id=action["object_id"],
        receipt_chain_verdict=receipt.verdict.value,
        receipt_chain_reason_code=receipt.reason_code,
        commit_gate_reached=True,
        commit_gate_code=gate_code,
        mutation_performed=mutation_performed,
    )


def prior_refusal_path(spec: Mapping[str, str]) -> MatrixResult:
    action = _action(spec)
    chain = Chain()
    _seed_prior_refusal(chain, action)
    return _bridge_evaluate(
        label=spec["label"],
        path="prior refusal",
        chain=chain,
        action=action,
        decision_id=f"matrix-blocked-{action['action_type']}",
        decision_record=_valid_authority_for(action),
    )


def clean_authority_path(spec: Mapping[str, str]) -> MatrixResult:
    action = _action(spec)
    chain = Chain()
    return _bridge_evaluate(
        label=spec["label"],
        path="clean + authority",
        chain=chain,
        action=action,
        decision_id=f"matrix-allowed-{action['action_type']}",
        decision_record=_valid_authority_for(action),
    )


def _print_result(index: int, result: MatrixResult) -> None:
    reached = str(result.commit_gate_reached).lower()
    mutated = str(result.mutation_performed).lower()
    gate_code = result.commit_gate_code or "NOT_REACHED"
    print(
        f"[{index}/6] {result.action_type:<16} "
        f"{result.path:<18} "
        f"chain={result.receipt_chain_verdict:<16} "
        f"gate_reached={reached:<5} "
        f"gate={gate_code:<25} "
        f"mutation={mutated}"
    )


def main() -> int:
    print("=" * 110)
    print("  receipt-chain-core — enterprise scenario matrix demo")
    print("  claim: same receipt-chain reachability pattern across enterprise-shaped actions")
    print("=" * 110)
    print()

    results: list[MatrixResult] = []
    for spec in SCENARIOS:
        results.append(prior_refusal_path(spec))
        results.append(clean_authority_path(spec))

    all_match = True
    for index, result in enumerate(results, start=1):
        _print_result(index, result)

        if result.path == "prior refusal":
            expected = ("HOLD", False, None, False)
        else:
            expected = ("ALLOW", True, "ALLOW", True)

        actual = (
            result.receipt_chain_verdict,
            result.commit_gate_reached,
            result.commit_gate_code,
            result.mutation_performed,
        )
        if actual != expected:
            all_match = False
            print(f"      expected={expected!r}")
            print(f"      actual  ={actual!r}")

    print()
    if all_match:
        print("ALL ENTERPRISE SCENARIOS PRODUCED EXPECTED RESULTS")
        return 0

    print("ENTERPRISE MATRIX MISMATCH — at least one scenario diverged from expectation")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
