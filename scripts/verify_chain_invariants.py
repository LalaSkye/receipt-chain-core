#!/usr/bin/env python3
"""Adversarial-vector verifier for receipt-chain-core.

Runs every invariant vector and writes a verification receipt to
``tests/adversarial/latest_verification_receipt.json``.

Exit code 0 on full pass, 1 on any failure.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipt_chain_core import (  # noqa: E402
    Chain,
    ChainStatus,
    ChainedReceipt,
    Verdict,
    evaluate,
    sha256_hex,
)
from receipt_chain_core.chain import REPLAY_SUPPRESS_THRESHOLD  # noqa: E402


VECTORS_PATH = ROOT / "tests" / "adversarial" / "INVARIANT_TEST_VECTORS_v1.json"
RECEIPT_PATH = ROOT / "tests" / "adversarial" / "latest_verification_receipt.json"
ISSUED = "2026-05-08T09:00:00Z"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _v01(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    last = None
    for i, a in enumerate(v["actions"]):
        last, _ = evaluate(chain, proposed_action=a,
                           decision_id=f"d-{i}", issued_at=ISSUED)
    ok = (chain.verify().value == v["expected_chain_status"]
          and last.verdict.value == v["expected_final_verdict"])
    return {"id": v["id"], "pass": ok}


def _v02(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    target = chain.receipts[v["mutate_index"]]
    chain.receipts[v["mutate_index"]] = replace(target, **{v["mutate_field"]: v["mutate_value"]})
    status = chain.verify().value
    return {"id": v["id"], "pass": status in v["expected_status_in"], "status": status}


def _v03(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    del chain.receipts[v["remove_index"]]
    status = chain.verify().value
    return {"id": v["id"], "pass": status == v["expected_status"], "status": status}


def _v04(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    for i, a in enumerate(v["seed_actions"]):
        evaluate(chain, proposed_action=a, decision_id=f"d-{i}", issued_at=ISSUED)
    i, j = v["swap"]
    chain.receipts[i], chain.receipts[j] = chain.receipts[j], chain.receipts[i]
    status = chain.verify().value
    return {"id": v["id"], "pass": status == v["expected_status"], "status": status}


def _v05(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    seed = ChainedReceipt.build(
        sequence=0, prev_receipt_hash=None, decision_id="d-seed",
        proposed_action=v["seed_refusal_for"], verdict=Verdict.HOLD,
        reason_code="upstream.refusal", reason="seeded", issued_at=ISSUED,
    )
    chain.append(seed)
    r, _ = evaluate(chain, proposed_action=v["proposed_action"],
                    decision_id="d-test", issued_at=ISSUED)
    ok = (r.verdict.value == v["expected_verdict"]
          and r.reason_code == v["expected_reason_code"])
    return {"id": v["id"], "pass": ok, "verdict": r.verdict.value, "reason_code": r.reason_code}


def _v06(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    blocked_seed = ChainedReceipt.build(
        sequence=0, prev_receipt_hash=None, decision_id="d-block",
        proposed_action=v["block_action"], verdict=Verdict.REBIND_REQUIRED,
        reason_code="seeded", reason="seeded", issued_at=ISSUED,
    )
    chain.append(blocked_seed)
    blocked, _ = evaluate(chain, proposed_action=v["block_action"],
                          decision_id="d-blocked-retry", issued_at=ISSUED)
    evaluate(chain,
             proposed_action={"action_type": "rebind", "object_id": v["object_id"]},
             decision_id="d-rebind", issued_at=ISSUED)
    cleared, _ = evaluate(chain, proposed_action=v["block_action"],
                          decision_id="d-cleared-retry", issued_at=ISSUED)
    ok = (blocked.verdict.value == v["expected_blocked_verdict"]
          and cleared.verdict.value == v["expected_after_rebind_verdict"])
    return {"id": v["id"], "pass": ok,
            "blocked": blocked.verdict.value, "cleared": cleared.verdict.value}


def _v07(v: Dict[str, Any]) -> Dict[str, Any]:
    a, b = Chain(), Chain()
    for i, action in enumerate(v["actions"]):
        evaluate(a, proposed_action=action,
                 decision_id=f"d-{i}", issued_at=v["issued_at"])
        evaluate(b, proposed_action=action,
                 decision_id=f"d-{i}", issued_at=v["issued_at"])
    ok = ([r.receipt_hash for r in a.receipts]
          == [r.receipt_hash for r in b.receipts])
    return {"id": v["id"], "pass": ok}


def _v08(v: Dict[str, Any]) -> Dict[str, Any]:
    chain = Chain()
    r, _ = evaluate(chain, proposed_action={"action_type": "send_email", "object_id": "msg-0"},
                    decision_id="d", issued_at=ISSUED)
    body = r.to_dict()
    ok = all(body[k] == ev for k, ev in zip(v["expected_keys"], v["expected_values"]))
    return {"id": v["id"], "pass": ok}


def _v09(v: Dict[str, Any]) -> Dict[str, Any]:
    """V09: replay suppression fires at REPLAY_SUPPRESS_THRESHOLD.

    Seeds seed_count ALLOW receipts for seed_action, then evaluates
    once more. Passes only if verdict and reason_code match expected.
    """
    chain = Chain()
    action = v["seed_action"]
    for i in range(v["seed_count"]):
        evaluate(chain, proposed_action=action,
                 decision_id=f"d-v09-seed-{i}", issued_at=ISSUED)
    r, _ = evaluate(chain, proposed_action=action,
                    decision_id="d-v09-test", issued_at=ISSUED)
    ok = (
        r.verdict.value == v["expected_verdict"]
        and r.reason_code == v["expected_reason_code"]
    )
    return {
        "id": v["id"],
        "pass": ok,
        "verdict": r.verdict.value,
        "reason_code": r.reason_code,
    }


HANDLERS = {
    "V01_clean_chain_of_three_verifies_ok": _v01,
    "V02_mutation_breaks_chain": _v02,
    "V03_removal_breaks_chain": _v03,
    "V04_reorder_breaks_chain": _v04,
    "V05_recent_refusal_changes_verdict": _v05,
    "V06_unresolved_rebind_blocks_then_clears": _v06,
    "V07_replay_is_deterministic": _v07,
    "V08_boundary_declarations_present": _v08,
    "V09_replay_suppression_fires_at_threshold": _v09,
}


def main() -> int:
    vectors = json.loads(VECTORS_PATH.read_text())["vectors"]
    results: List[Dict[str, Any]] = []
    for v in vectors:
        handler = HANDLERS.get(v["id"])
        if handler is None:
            results.append({"id": v["id"], "pass": False, "error": "no_handler"})
            continue
        try:
            results.append(handler(v))
        except Exception as exc:  # pragma: no cover — diagnostic path
            results.append({"id": v["id"], "pass": False, "error": repr(exc)})

    all_pass = all(r["pass"] for r in results)

    receipt_body = {
        "schema": "receipt_chain_core.verification_receipt.v0.1",
        "issued_at": _now_iso(),
        "vectors_path": str(VECTORS_PATH.relative_to(ROOT)),
        "vector_count": len(results),
        "all_pass": all_pass,
        "results": results,
        "boundary_declaration": {
            "does_not_execute": True,
            "does_not_bind_consequence": True,
        },
    }
    receipt_body["receipt_hash"] = sha256_hex(receipt_body)
    RECEIPT_PATH.write_text(json.dumps(receipt_body, indent=2, sort_keys=True) + "\n")

    print(json.dumps({
        "all_pass": all_pass,
        "vector_count": len(results),
        "receipt_path": str(RECEIPT_PATH.relative_to(ROOT)),
        "receipt_hash": receipt_body["receipt_hash"][:16] + "...",
    }, indent=2, sort_keys=True))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
