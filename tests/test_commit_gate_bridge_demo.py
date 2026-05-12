"""Tests for the receipt-chain → commit-gate bridge demo.

These tests keep the bridge claim narrow:
    receipt-chain state controls whether the local commit-boundary adapter is reached.

They do not test production integration with commit-gate-core.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "examples" / "commit_gate_bridge_demo.py"

spec = importlib.util.spec_from_file_location("commit_gate_bridge_demo", DEMO_PATH)
assert spec is not None
assert spec.loader is not None
bridge_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_demo)


def test_prior_refusal_blocks_before_commit_gate() -> None:
    result = bridge_demo.scenario_chain_blocks_before_commit_gate()

    assert result.receipt_chain_verdict == "HOLD"
    assert result.receipt_chain_reason_code == "chain.recent_refusal_in_window"
    assert result.commit_gate_reached is False
    assert result.commit_gate_code is None
    assert result.mutation_performed is False


def test_clean_chain_with_missing_authority_reaches_gate_but_does_not_mutate() -> None:
    result = bridge_demo.scenario_clean_chain_missing_authority()

    assert result.receipt_chain_verdict == "ALLOW"
    assert result.receipt_chain_reason_code == "chain.clean_no_blocking_state"
    assert result.commit_gate_reached is True
    assert result.commit_gate_code == "DENY:NO_DECISION_RECORD"
    assert result.mutation_performed is False


def test_clean_chain_with_valid_authority_reaches_gate_and_mutates_locally() -> None:
    result = bridge_demo.scenario_clean_chain_valid_authority()

    assert result.receipt_chain_verdict == "ALLOW"
    assert result.receipt_chain_reason_code == "chain.clean_no_blocking_state"
    assert result.commit_gate_reached is True
    assert result.commit_gate_code == "ALLOW"
    assert result.mutation_performed is True


def test_bridge_demo_main_exits_zero_when_expected_paths_hold() -> None:
    assert bridge_demo.main() == 0
