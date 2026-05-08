"""04 — recent refusal changes verdict.

Same proposed action evaluated against two chains:
- empty chain         -> ALLOW
- chain with a recent HOLD on the same action+object -> HOLD
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import (  # noqa: E402
    Chain,
    ChainedReceipt,
    Verdict,
    evaluate,
)


def main() -> None:
    proposed = {"action_type": "send_email", "object_id": "msg-001"}
    issued = "2026-05-08T09:00:00Z"

    # clean chain
    a = Chain()
    r1, _ = evaluate(a, proposed_action=proposed, decision_id="dec-A", issued_at=issued)

    # chain with a manually-injected HOLD for the same action+object
    b = Chain()
    seed = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="dec-prior-refusal",
        proposed_action=proposed,
        verdict=Verdict.HOLD,
        reason_code="upstream.refusal",
        reason="seeded refusal for example",
        issued_at=issued,
    )
    b.append(seed)
    r2, _ = evaluate(b, proposed_action=proposed, decision_id="dec-B", issued_at=issued)

    print(json.dumps({
        "clean_chain_verdict": r1.verdict.value,
        "chain_with_recent_refusal_verdict": r2.verdict.value,
        "reason_code_b": r2.reason_code,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
