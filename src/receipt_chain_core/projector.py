"""Prior-state projector v0.1.

Turns a sequence of ChainedReceipts into a small, well-defined
ProjectedState that the next admissibility decision is allowed to read.

Schema: receipt_chain_core.projector.v0.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .hashing import sha256_hex
from .receipt import ChainedReceipt, PROJECTOR_SCHEMA_ID
from .verdict import ChainStatus, Verdict


REFUSAL_WINDOW = 5  # last N receipts considered for "recent" inputs


@dataclass(frozen=True)
class ProjectedState:
    """Output of the projector — the only chain-derived input the next
    admissibility decision is allowed to read."""

    schema: str
    chain_status: ChainStatus
    head_sequence: Optional[int]
    recent_refusal: Optional[Dict[str, Any]]
    unresolved_rebind: bool
    replay_attempt_count: int
    refusal_window: int = REFUSAL_WINDOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "chain_status": self.chain_status.value,
            "head_sequence": self.head_sequence,
            "recent_refusal": self.recent_refusal,
            "unresolved_rebind": self.unresolved_rebind,
            "replay_attempt_count": self.replay_attempt_count,
            "refusal_window": self.refusal_window,
        }


def _proposed_action_hash(action: Mapping[str, Any]) -> str:
    return sha256_hex({"action_type": action["action_type"], "object_id": action["object_id"]})


def project(
    receipts: Sequence[ChainedReceipt],
    proposed_action: Mapping[str, Any],
    chain_status: ChainStatus,
) -> ProjectedState:
    """Project a chain into the state the next decision may read.

    The projector is deterministic: same inputs → same output.
    """

    if chain_status != ChainStatus.OK:
        return ProjectedState(
            schema=PROJECTOR_SCHEMA_ID,
            chain_status=chain_status,
            head_sequence=(receipts[-1].sequence if receipts else None),
            recent_refusal=None,
            unresolved_rebind=False,
            replay_attempt_count=0,
            refusal_window=REFUSAL_WINDOW,
        )

    if not receipts:
        return ProjectedState(
            schema=PROJECTOR_SCHEMA_ID,
            chain_status=ChainStatus.EMPTY,
            head_sequence=None,
            recent_refusal=None,
            unresolved_rebind=False,
            replay_attempt_count=0,
            refusal_window=REFUSAL_WINDOW,
        )

    window: List[ChainedReceipt] = list(receipts[-REFUSAL_WINDOW:])
    proposed_hash = _proposed_action_hash(proposed_action)

    # recent_refusal: most recent DENY/HOLD in window matching the same
    # action_type AND object_id as the proposed action
    recent_refusal: Optional[Dict[str, Any]] = None
    for r in reversed(window):
        if r.verdict in (Verdict.DENY, Verdict.HOLD):
            if (
                r.proposed_action.get("action_type") == proposed_action["action_type"]
                and r.proposed_action.get("object_id") == proposed_action["object_id"]
            ):
                recent_refusal = {
                    "sequence": r.sequence,
                    "decision_id": r.decision_id,
                    "verdict": r.verdict.value,
                    "reason_code": r.reason_code,
                }
                break

    # unresolved_rebind: any REBIND_REQUIRED for this object_id, anywhere
    # in the chain, that is not followed by a successful rebind receipt
    # for the same object_id at a later sequence.
    unresolved_rebind = _unresolved_rebind(
        receipts, object_id=proposed_action["object_id"]
    )

    # replay_attempt_count: receipts in window with same canonical
    # action hash as the proposal
    replay_attempt_count = sum(
        1
        for r in window
        if _proposed_action_hash(r.proposed_action) == proposed_hash
    )

    return ProjectedState(
        schema=PROJECTOR_SCHEMA_ID,
        chain_status=ChainStatus.OK,
        head_sequence=receipts[-1].sequence,
        recent_refusal=recent_refusal,
        unresolved_rebind=unresolved_rebind,
        replay_attempt_count=replay_attempt_count,
        refusal_window=REFUSAL_WINDOW,
    )


def _unresolved_rebind(
    receipts: Sequence[ChainedReceipt], *, object_id: str
) -> bool:
    """Walk the chain in order. For the given object_id, return True if
    the most recent REBIND_REQUIRED has not been followed by a later
    rebind receipt with verdict ALLOW."""

    last_rebind_required_seq: Optional[int] = None
    last_rebind_clear_seq: Optional[int] = None

    for r in receipts:
        if r.proposed_action.get("object_id") != object_id:
            continue
        if r.verdict == Verdict.REBIND_REQUIRED:
            last_rebind_required_seq = r.sequence
        elif (
            r.proposed_action.get("action_type") == "rebind"
            and r.verdict == Verdict.ALLOW
        ):
            last_rebind_clear_seq = r.sequence

    if last_rebind_required_seq is None:
        return False
    if last_rebind_clear_seq is None:
        return True
    return last_rebind_clear_seq < last_rebind_required_seq
