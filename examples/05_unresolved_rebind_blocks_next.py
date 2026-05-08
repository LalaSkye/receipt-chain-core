"""05 — unresolved REBIND_REQUIRED blocks next call until rebind appended.

Sequence:
1. Seed a REBIND_REQUIRED for object_id obj-X.
2. Try to send_email on obj-X       -> REBIND_REQUIRED
3. Append a successful rebind on obj-X.
4. Retry the original action        -> ALLOW
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import Chain, ChainedReceipt, Verdict, evaluate  # noqa: E402


def main() -> None:
    issued = "2026-05-08T09:00:00Z"
    chain = Chain()

    # 1. seed unresolved REBIND_REQUIRED on obj-X
    seed = ChainedReceipt.build(
        sequence=0,
        prev_receipt_hash=None,
        decision_id="dec-seed-rebind",
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded.rebind_required",
        reason="seeded REBIND_REQUIRED for example",
        issued_at=issued,
    )
    chain.append(seed)

    # 2. try the action -> REBIND_REQUIRED
    r1, _ = evaluate(
        chain,
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        decision_id="dec-blocked",
        issued_at=issued,
    )

    # 3. append a successful rebind for obj-X
    r2, _ = evaluate(
        chain,
        proposed_action={"action_type": "rebind", "object_id": "obj-X"},
        decision_id="dec-rebind",
        issued_at=issued,
    )

    # 4. retry the original action
    r3, _ = evaluate(
        chain,
        proposed_action={"action_type": "send_email", "object_id": "obj-X"},
        decision_id="dec-retry",
        issued_at=issued,
    )

    print(json.dumps({
        "blocked_verdict": r1.verdict.value,
        "rebind_verdict": r2.verdict.value,
        "retry_verdict": r3.verdict.value,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
