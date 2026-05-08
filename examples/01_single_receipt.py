"""01 — single receipt.

Empty chain + clean proposed action -> ALLOW.
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
    receipt, state = evaluate(
        chain,
        proposed_action={"action_type": "send_email", "object_id": "msg-001"},
        decision_id="dec-0001",
        issued_at="2026-05-08T09:00:00Z",
    )
    print(json.dumps({"verdict": receipt.verdict.value,
                      "reason_code": receipt.reason_code,
                      "head": chain.head(),
                      "state": state.to_dict()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
