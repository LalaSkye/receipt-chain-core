"""receipt_chain_core v0.1

Prior receipt state participates in the next admissibility decision.

Public surface:
    Verdict           — verdict enum
    ChainStatus       — chain verifier status enum
    ChainedReceipt    — one receipt in a chain
    Chain             — sequence of chained receipts with verifier
    ProjectedState    — output of the prior-state projector
    project           — project chain into ProjectedState
    evaluate          — evaluate a proposed action against a chain
    canonical_json    — deterministic JSON
    sha256_hex        — sha256 over canonical JSON

Schema versions:
    receipt_chain_core.receipt.v0.1
    receipt_chain_core.projector.v0.1
"""

from .verdict import Verdict, ChainStatus
from .hashing import canonical_json, sha256_hex
from .receipt import ChainedReceipt
from .projector import ProjectedState, project, REFUSAL_WINDOW
from .chain import Chain, evaluate

__all__ = [
    "Verdict",
    "ChainStatus",
    "ChainedReceipt",
    "Chain",
    "ProjectedState",
    "project",
    "evaluate",
    "canonical_json",
    "sha256_hex",
    "REFUSAL_WINDOW",
]

__version__ = "0.1.0"
