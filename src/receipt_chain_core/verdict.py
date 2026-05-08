"""Closed enums used by the kernel."""

from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    """Verdicts the kernel may emit.

    The set is closed. No silent fall-through.
    """

    ALLOW = "ALLOW"
    HOLD = "HOLD"
    DENY = "DENY"
    REBIND_REQUIRED = "REBIND_REQUIRED"


class ChainStatus(str, Enum):
    """Outcome of running the chain verifier."""

    OK = "OK"
    EMPTY = "EMPTY"
    BROKEN_LINK = "BROKEN_LINK"
    BROKEN_SEQUENCE = "BROKEN_SEQUENCE"
    BROKEN_HASH = "BROKEN_HASH"
