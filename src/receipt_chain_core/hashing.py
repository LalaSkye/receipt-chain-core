"""Canonical JSON and SHA-256 helpers.

Determinism rules:
- keys sorted at every level
- separators (",", ":")
- ensure_ascii=False
- UTF-8 encoded before hashing
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return the canonical JSON serialisation of ``value``.

    Two structurally identical objects always produce identical strings.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_hex(value: Any) -> str:
    """Return the lowercase hex SHA-256 digest of ``canonical_json(value)``."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
