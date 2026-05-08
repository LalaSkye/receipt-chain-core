"""03 — tamper breaks chain.

Build a clean chain, mutate one past receipt, show the verifier returns
BROKEN_HASH and the next evaluate returns HOLD.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import Chain, evaluate  # noqa: E402


def main() -> None:
    chain = Chain()
    issued = "2026-05-08T09:00:00Z"
    for i in range(2):
        evaluate(chain,
                 proposed_action={"action_type": "send_email", "object_id": f"msg-{i}"},
                 decision_id=f"dec-{i:04d}",
                 issued_at=issued)

    print("before tamper:", chain.verify().value)

    # mutate a past receipt by replacing it with a structurally-altered copy
    target = chain.receipts[0]
    chain.receipts[0] = replace(target, reason="ALTERED")

    print("after tamper :", chain.verify().value)

    receipt, state = evaluate(chain,
                              proposed_action={"action_type": "send_email", "object_id": "msg-9"},
                              decision_id="dec-tamper",
                              issued_at=issued)
    print(json.dumps({"verdict": receipt.verdict.value,
                      "reason_code": receipt.reason_code,
                      "chain_status_seen": state.chain_status.value}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
