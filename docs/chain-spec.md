# Chain Specification v0.1

## Canonical hashing

All hashes are SHA-256 over canonical JSON:

- UTF-8 encoded
- keys sorted lexicographically at every level
- no insignificant whitespace (`separators=(",", ":")`)
- `ensure_ascii=False`

This produces a deterministic byte sequence for any JSON-serializable
object. Two structurally identical objects always hash to the same digest.

## ChainedReceipt fields

A v0.1 chained receipt is a JSON object with the following required keys:

| Field | Type | Meaning |
|---|---|---|
| `schema` | const string `"receipt_chain_core.receipt.v0.1"` | schema identifier |
| `sequence` | integer ≥ 0 | strict-monotonic position in chain |
| `prev_receipt_hash` | string or null | canonical hash of receipt at `sequence - 1`; null only for sequence 0 |
| `decision_id` | string | identifier of the admissibility decision recorded here |
| `proposed_action` | object | action that was evaluated, with `action_type` and `object_id` |
| `verdict` | enum | one of `ALLOW`, `HOLD`, `DENY`, `REBIND_REQUIRED` |
| `reason_code` | string | machine-readable reason |
| `reason` | string | human-readable reason |
| `does_not_execute` | const `true` | boundary declaration |
| `does_not_bind_consequence` | const `true` | boundary declaration |
| `issued_at` | string | RFC 3339 UTC timestamp |
| `receipt_hash` | string | canonical SHA-256 of the receipt with `receipt_hash` field removed |

## Chain head

The chain head is a small structure:

| Field | Meaning |
|---|---|
| `length` | number of receipts in chain |
| `head_sequence` | sequence number of the most recent receipt |
| `head_hash` | canonical hash of the most recent receipt |

The head is recomputed deterministically. It is not stored
authoritatively — the receipts themselves are the source of truth.

## Append rule

`append(chain, decision)` constructs a new `ChainedReceipt` such that:

- `sequence = chain.head_sequence + 1` (or 0 if empty)
- `prev_receipt_hash = chain.head_hash` (or null if empty)
- `receipt_hash` is computed last, after all other fields are populated

The chain is verified after the append. If verification fails, the append
is rejected and the chain is unchanged.

## Verification rule

`verify(chain)` returns one of:

| Outcome | Meaning |
|---|---|
| `OK` | every receipt links correctly, sequence is strict-monotonic, all hashes match |
| `BROKEN_LINK` | a `prev_receipt_hash` does not match the prior receipt's canonical hash |
| `BROKEN_SEQUENCE` | sequence numbers are not strict-monotonic from 0 |
| `BROKEN_HASH` | a receipt's `receipt_hash` does not match its canonical recomputation |
| `EMPTY` | chain has no receipts |

`OK` is the only outcome that allows the next admissibility decision to
treat the chain as a verified link.

## Tamper resistance

Three tamper modes are required to be detectable:

1. **Mutation** — any field changed in any receipt → `BROKEN_HASH`
   (recomputed `receipt_hash` no longer matches), and on the next-receipt
   path the linkage is `BROKEN_LINK`.
2. **Removal** — receipt N dropped → next receipt's `prev_receipt_hash`
   no longer matches the new neighbour → `BROKEN_LINK` and
   `BROKEN_SEQUENCE`.
3. **Reorder** — two receipts swapped → `BROKEN_LINK` and
   `BROKEN_SEQUENCE`.

All three are tested in `tests/test_tamper_detection.py`.

## Determinism

For any chain `C` and proposed action `A`:

```
verdict(C, A) is a pure function of:
    canonical_hash(C)
    canonical_hash(A)
    projector schema version
```

There is no time-of-day input, no randomness, no external state.

`issued_at` is supplied by the caller, not generated inside `evaluate`. Two
callers with the same `issued_at` produce identical receipts.
