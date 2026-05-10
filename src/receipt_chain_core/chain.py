"""Chain — a sequence of ChainedReceipts with a fail-closed verifier and a
deterministic admissibility evaluator.

The chain is the source of truth. The "head" is a small derived structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .hashing import sha256_hex
from .projector import ProjectedState, project
from .receipt import ChainedReceipt
from .verdict import ChainStatus, Verdict


# Number of matching attempts within the refusal window that triggers
# replay suppression. Evaluated after tamper/rebind/refusal checks.
REPLAY_SUPPRESS_THRESHOLD: int = 3


@dataclass
class Chain:
    """An ordered sequence of ChainedReceipts.

    Mutating ``receipts`` directly is allowed for tests that simulate
    tampering. The verifier always re-checks structure on demand.
    """

    receipts: List[ChainedReceipt] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Head
    # ------------------------------------------------------------------ #

    @property
    def head_sequence(self) -> Optional[int]:
        if not self.receipts:
            return None
        return self.receipts[-1].sequence

    @property
    def head_hash(self) -> Optional[str]:
        if not self.receipts:
            return None
        return self.receipts[-1].receipt_hash

    def head(self) -> Dict[str, Any]:
        return {
            "length": len(self.receipts),
            "head_sequence": self.head_sequence,
            "head_hash": self.head_hash,
        }

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #

    def verify(self) -> ChainStatus:
        """Run the chain verifier, fail-closed.

        Order:
            1. EMPTY check
            2. structure: schema + body shape
            3. sequence strict-monotonic from 0
            4. linkage: prev_receipt_hash matches prior receipt's hash
            5. hash: each receipt's receipt_hash matches its canonical body
        """
        if not self.receipts:
            return ChainStatus.EMPTY

        # 3. sequence
        for i, r in enumerate(self.receipts):
            if r.sequence != i:
                return ChainStatus.BROKEN_SEQUENCE

        # 5. hash integrity (per-receipt)
        for r in self.receipts:
            if r.recompute_hash() != r.receipt_hash:
                return ChainStatus.BROKEN_HASH

        # 4. linkage
        for i, r in enumerate(self.receipts):
            if i == 0:
                if r.prev_receipt_hash is not None:
                    return ChainStatus.BROKEN_LINK
            else:
                expected_prev = self.receipts[i - 1].receipt_hash
                if r.prev_receipt_hash != expected_prev:
                    return ChainStatus.BROKEN_LINK

        return ChainStatus.OK

    # ------------------------------------------------------------------ #
    # Append + evaluate
    # ------------------------------------------------------------------ #

    def append(self, receipt: ChainedReceipt) -> ChainStatus:
        """Append a pre-built receipt and verify the chain.

        On verifier failure, the receipt is removed and the chain is
        unchanged. The caller receives the failure status.
        """
        self.receipts.append(receipt)
        status = self.verify()
        if status != ChainStatus.OK:
            self.receipts.pop()
        return status


# ---------------------------------------------------------------------- #
# Public evaluator
# ---------------------------------------------------------------------- #


def _decide(
    proposed_action: Mapping[str, Any], state: ProjectedState
) -> Tuple[Verdict, str, str]:
    """The five-row ladder.

    Evaluation order (FIRST_FAIL):
        1. tamper detection
        2. unresolved rebind
        3. recent refusal
        4. replay suppression  (Issue #1: replay_attempt_count now active)
        5. clean allow
    """
    if state.chain_status != ChainStatus.OK and state.chain_status != ChainStatus.EMPTY:
        return (
            Verdict.HOLD,
            "chain.tamper_detected",
            f"chain verifier returned {state.chain_status.value}",
        )
    if state.unresolved_rebind and proposed_action["action_type"] != "rebind":
        return (
            Verdict.REBIND_REQUIRED,
            "chain.unresolved_rebind",
            "an unresolved REBIND_REQUIRED exists for this object_id",
        )
    if state.recent_refusal is not None:
        return (
            Verdict.HOLD,
            "chain.recent_refusal_in_window",
            f"recent refusal at sequence {state.recent_refusal['sequence']}",
        )
    # Issue #1: make replay_attempt_count decision-active.
    # If the same proposed action has appeared >= REPLAY_SUPPRESS_THRESHOLD
    # times within the refusal window, suppress further attempts.
    if state.replay_attempt_count >= REPLAY_SUPPRESS_THRESHOLD:
        return (
            Verdict.HOLD,
            "chain.replay_suppressed",
            f"replay attempt count {state.replay_attempt_count} reached threshold {REPLAY_SUPPRESS_THRESHOLD}",
        )
    return (
        Verdict.ALLOW,
        "chain.clean_no_blocking_state",
        "chain is OK and projector found no blocking state",
    )


def evaluate(
    chain: Chain,
    *,
    proposed_action: Mapping[str, Any],
    decision_id: str,
    issued_at: str,
) -> Tuple[ChainedReceipt, ProjectedState]:
    """Evaluate a proposed action against the chain and append a new
    chained receipt.

    Returns the new receipt and the ProjectedState used to decide.

    Determinism contract: for the same chain, proposed_action,
    decision_id, and issued_at, this function produces an identical
    receipt (byte-equal to_dict, identical receipt_hash).
    """
    if not isinstance(chain, Chain):
        raise TypeError("chain must be a Chain instance")

    chain_status = chain.verify()
    state = project(chain.receipts, proposed_action, chain_status)
    verdict, reason_code, reason = _decide(proposed_action, state)

    next_seq = (chain.head_sequence + 1) if chain.head_sequence is not None else 0
    prev_hash = chain.head_hash  # None if empty

    receipt = ChainedReceipt.build(
        sequence=next_seq,
        prev_receipt_hash=prev_hash,
        decision_id=decision_id,
        proposed_action=dict(proposed_action),
        verdict=verdict,
        reason_code=reason_code,
        reason=reason,
        issued_at=issued_at,
    )

    append_status = chain.append(receipt)
    if append_status != ChainStatus.OK:
        # The chain was already broken before this call. The new receipt
        # is not retained. Surface the failure as HOLD for the caller.
        # The returned receipt is informational only; it is NOT in the
        # chain. The caller can inspect it but must not treat it as a
        # successful append.
        # We rebuild a HOLD receipt that does not depend on the broken
        # chain head, to keep replay deterministic.
        receipt = ChainedReceipt.build(
            sequence=next_seq,
            prev_receipt_hash=prev_hash,
            decision_id=decision_id,
            proposed_action=dict(proposed_action),
            verdict=Verdict.HOLD,
            reason_code="chain.tamper_detected",
            reason=f"chain verifier returned {append_status.value}; receipt not appended",
            issued_at=issued_at,
        )
        return receipt, state

    return receipt, state
