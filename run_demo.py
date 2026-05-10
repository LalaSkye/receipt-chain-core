#!/usr/bin/env python3
"""run_demo.py — receipt-chain-core demonstration.

Six scenarios, one summary line each. No dependencies beyond stdlib.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import (  # noqa: E402
    Chain,
    ChainStatus,
    ChainedReceipt,
    Verdict,
    evaluate,
)
from receipt_chain_core.chain import REPLAY_SUPPRESS_THRESHOLD  # noqa: E402


ISSUED = "2026-05-08T09:00:00Z"


def _row(label: str, verdict: str, reason_code: str) -> str:
    return f"  [{verdict:>16}]  {label:<36}  ({reason_code})"


def _scenario_clean() -> tuple[str, str, str]:
    chain = Chain()
    r, _ = evaluate(chain,
                    proposed_action={"action_type": "send_email", "object_id": "msg-0"},
                    decision_id="d-clean", issued_at=ISSUED)
    return ("clean chain", r.verdict.value, r.reason_code)


def _scenario_recent_refusal() -> tuple[str, str, str]:
    chain = Chain()
    action = {"action_type": "send_email", "object_id": "msg-A"}
    seed = ChainedReceipt.build(
        sequence=0, prev_receipt_hash=None, decision_id="d-prior",
        proposed_action=action, verdict=Verdict.HOLD,
        reason_code="upstream.refusal", reason="seeded", issued_at=ISSUED)
    chain.append(seed)
    r, _ = evaluate(chain, proposed_action=action,
                    decision_id="d-after", issued_at=ISSUED)
    return ("recent refusal in window", r.verdict.value, r.reason_code)


def _scenario_unresolved_rebind() -> tuple[str, str, str]:
    chain = Chain()
    action = {"action_type": "send_email", "object_id": "obj-X"}
    seed = ChainedReceipt.build(
        sequence=0, prev_receipt_hash=None, decision_id="d-block",
        proposed_action=action, verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded", reason="seeded", issued_at=ISSUED)
    chain.append(seed)
    r, _ = evaluate(chain, proposed_action=action,
                    decision_id="d-blocked-retry", issued_at=ISSUED)
    return ("unresolved REBIND_REQUIRED", r.verdict.value, r.reason_code)


def _scenario_rebind_clears() -> tuple[str, str, str]:
    chain = Chain()
    action = {"action_type": "send_email", "object_id": "obj-Y"}
    seed = ChainedReceipt.build(
        sequence=0, prev_receipt_hash=None, decision_id="d-block",
        proposed_action=action, verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded", reason="seeded", issued_at=ISSUED)
    chain.append(seed)
    evaluate(chain,
             proposed_action={"action_type": "rebind", "object_id": "obj-Y"},
             decision_id="d-rebind", issued_at=ISSUED)
    r, _ = evaluate(chain, proposed_action=action,
                    decision_id="d-retry", issued_at=ISSUED)
    return ("rebind appended, retry", r.verdict.value, r.reason_code)


def _scenario_tampered() -> tuple[str, str, str]:
    chain = Chain()
    for i in range(2):
        evaluate(chain,
                 proposed_action={"action_type": "send_email", "object_id": f"msg-{i}"},
                 decision_id=f"d-{i}", issued_at=ISSUED)
    chain.receipts[0] = replace(chain.receipts[0], reason="ALTERED")
    r, _ = evaluate(chain,
                    proposed_action={"action_type": "send_email", "object_id": "msg-9"},
                    decision_id="d-tamper", issued_at=ISSUED)
    return ("tampered chain", r.verdict.value, r.reason_code)


def _scenario_replay_suppression() -> tuple[str, str, str]:
    """Scenario 6: replay suppression fires at REPLAY_SUPPRESS_THRESHOLD.

    Seeds exactly REPLAY_SUPPRESS_THRESHOLD ALLOW receipts for the same
    action. The next evaluation sees replay_attempt_count == threshold
    and returns HOLD / chain.replay_suppressed.
    """
    chain = Chain()
    action = {"action_type": "send_email", "object_id": "msg-replay"}
    for i in range(REPLAY_SUPPRESS_THRESHOLD):
        evaluate(chain, proposed_action=action,
                 decision_id=f"d-seed-{i}", issued_at=ISSUED)
    r, _ = evaluate(chain, proposed_action=action,
                    decision_id="d-suppressed", issued_at=ISSUED)
    return ("replay suppression at threshold", r.verdict.value, r.reason_code)


def main() -> int:
    print("=" * 74)
    print("  receipt-chain-core — demo (yesterday's receipt changes today's door)")
    print("=" * 74)
    print()
    expected = [
        (_scenario_clean(),                  "ALLOW"),
        (_scenario_recent_refusal(),         "HOLD"),
        (_scenario_unresolved_rebind(),      "REBIND_REQUIRED"),
        (_scenario_rebind_clears(),          "ALLOW"),
        (_scenario_tampered(),               "HOLD"),
        (_scenario_replay_suppression(),     "HOLD"),
    ]
    all_match = True
    for (label, verdict, reason_code), expected_verdict in expected:
        print(_row(label, verdict, reason_code))
        if verdict != expected_verdict:
            all_match = False
    print()
    if all_match:
        print("  ALL DEMO SCENARIOS PRODUCED EXPECTED VERDICTS")
        return 0
    print("  DEMO MISMATCH — at least one scenario diverged from expectation")
    return 1


if __name__ == "__main__":
    sys.exit(main())
