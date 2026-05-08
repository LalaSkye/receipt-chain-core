"""ChainedReceipt — the unit of evidence in a chain.

A ChainedReceipt records one admissibility decision and the link to the
prior chain state. It is intentionally small. Receipts are immutable once
constructed.

Schema id: receipt_chain_core.receipt.v0.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from .hashing import sha256_hex
from .verdict import Verdict


SCHEMA_ID = "receipt_chain_core.receipt.v0.1"
PROJECTOR_SCHEMA_ID = "receipt_chain_core.projector.v0.1"


REQUIRED_PROPOSED_ACTION_FIELDS = ("action_type", "object_id")


def _validate_proposed_action(action: Mapping[str, Any]) -> None:
    if not isinstance(action, Mapping):
        raise ValueError("proposed_action must be a mapping")
    missing = [k for k in REQUIRED_PROPOSED_ACTION_FIELDS if k not in action]
    if missing:
        raise ValueError(
            f"proposed_action missing required fields: {missing}"
        )
    if not isinstance(action["action_type"], str) or not action["action_type"]:
        raise ValueError("proposed_action.action_type must be a non-empty string")
    if not isinstance(action["object_id"], str) or not action["object_id"]:
        raise ValueError("proposed_action.object_id must be a non-empty string")


@dataclass(frozen=True)
class ChainedReceipt:
    """One immutable chained receipt."""

    sequence: int
    prev_receipt_hash: Optional[str]
    decision_id: str
    proposed_action: Dict[str, Any]
    verdict: Verdict
    reason_code: str
    reason: str
    issued_at: str
    receipt_hash: str = field(default="")
    schema: str = SCHEMA_ID
    projector_schema: str = PROJECTOR_SCHEMA_ID
    does_not_execute: bool = True
    does_not_bind_consequence: bool = True

    @staticmethod
    def build(
        *,
        sequence: int,
        prev_receipt_hash: Optional[str],
        decision_id: str,
        proposed_action: Mapping[str, Any],
        verdict: Verdict,
        reason_code: str,
        reason: str,
        issued_at: str,
    ) -> "ChainedReceipt":
        """Construct a fully-populated, hash-bound receipt.

        Validation is STRUCTURE_FIRST. Missing or malformed fields raise
        ValueError before any hashing occurs.
        """
        if not isinstance(sequence, int) or sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if sequence == 0 and prev_receipt_hash is not None:
            raise ValueError("sequence 0 must have prev_receipt_hash=None")
        if sequence > 0 and not isinstance(prev_receipt_hash, str):
            raise ValueError("sequence>0 requires a string prev_receipt_hash")
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        if not isinstance(verdict, Verdict):
            raise ValueError("verdict must be a Verdict enum value")
        if not isinstance(reason_code, str) or not reason_code:
            raise ValueError("reason_code must be a non-empty string")
        if not isinstance(reason, str):
            raise ValueError("reason must be a string")
        if not isinstance(issued_at, str) or not issued_at:
            raise ValueError("issued_at must be a non-empty string")
        _validate_proposed_action(proposed_action)

        body: Dict[str, Any] = {
            "schema": SCHEMA_ID,
            "projector_schema": PROJECTOR_SCHEMA_ID,
            "sequence": sequence,
            "prev_receipt_hash": prev_receipt_hash,
            "decision_id": decision_id,
            "proposed_action": dict(proposed_action),
            "verdict": verdict.value,
            "reason_code": reason_code,
            "reason": reason,
            "issued_at": issued_at,
            "does_not_execute": True,
            "does_not_bind_consequence": True,
        }
        receipt_hash = sha256_hex(body)

        return ChainedReceipt(
            sequence=sequence,
            prev_receipt_hash=prev_receipt_hash,
            decision_id=decision_id,
            proposed_action=dict(proposed_action),
            verdict=verdict,
            reason_code=reason_code,
            reason=reason,
            issued_at=issued_at,
            receipt_hash=receipt_hash,
            schema=SCHEMA_ID,
            projector_schema=PROJECTOR_SCHEMA_ID,
            does_not_execute=True,
            does_not_bind_consequence=True,
        )

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """Return the canonical-form dict, including ``receipt_hash``."""
        out: Dict[str, Any] = {
            "schema": self.schema,
            "projector_schema": self.projector_schema,
            "sequence": self.sequence,
            "prev_receipt_hash": self.prev_receipt_hash,
            "decision_id": self.decision_id,
            "proposed_action": dict(self.proposed_action),
            "verdict": self.verdict.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "issued_at": self.issued_at,
            "does_not_execute": self.does_not_execute,
            "does_not_bind_consequence": self.does_not_bind_consequence,
            "receipt_hash": self.receipt_hash,
        }
        return out

    def body_for_hash(self) -> Dict[str, Any]:
        """Return the canonical body used to compute ``receipt_hash``.

        This is the dict with ``receipt_hash`` stripped.
        """
        body = self.to_dict()
        body.pop("receipt_hash", None)
        return body

    def recompute_hash(self) -> str:
        return sha256_hex(self.body_for_hash())

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ChainedReceipt":
        """Reconstruct a ChainedReceipt from a mapping.

        This does not re-validate hashes — that is the verifier's job.
        """
        if data.get("schema") != SCHEMA_ID:
            raise ValueError(f"unsupported receipt schema: {data.get('schema')!r}")
        return ChainedReceipt(
            sequence=int(data["sequence"]),
            prev_receipt_hash=data.get("prev_receipt_hash"),
            decision_id=str(data["decision_id"]),
            proposed_action=dict(data["proposed_action"]),
            verdict=Verdict(data["verdict"]),
            reason_code=str(data["reason_code"]),
            reason=str(data["reason"]),
            issued_at=str(data["issued_at"]),
            receipt_hash=str(data["receipt_hash"]),
            schema=SCHEMA_ID,
            projector_schema=str(data.get("projector_schema", PROJECTOR_SCHEMA_ID)),
            does_not_execute=bool(data.get("does_not_execute", True)),
            does_not_bind_consequence=bool(data.get("does_not_bind_consequence", True)),
        )
