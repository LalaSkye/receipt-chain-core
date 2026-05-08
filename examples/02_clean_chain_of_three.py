"""02 — clean chain of three.

Three different actions on different objects -> all ALLOW.
Verifier returns OK at the end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import Chain, evaluate  # noqa: E402


def main() -> None:
    chain = Chain()
    actions = [
        ({"action_type": "send_email", "object_id": "msg-001"}, "dec-0001"),
        ({"action_type": "publish_post", "object_id": "post-002"}, "dec-0002"),
        ({"action_type": "rotate_key", "object_id": "kek-003"}, "dec-0003"),
    ]
    issued = "2026-05-08T09:00:00Z"

    results = []
    for action, decision_id in actions:
        r, _ = evaluate(chain, proposed_action=action,
                        decision_id=decision_id, issued_at=issued)
        results.append({"sequence": r.sequence,
                        "verdict": r.verdict.value,
                        "receipt_hash": r.receipt_hash[:12] + "..."})

    print(json.dumps({"chain_status": chain.verify().value,
                      "head": chain.head(),
                      "receipts": results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
