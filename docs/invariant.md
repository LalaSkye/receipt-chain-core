# Core Invariant

## Statement

A new admissibility decision is invalid unless it carries a verified link to
the prior chain state.

If the link cannot be verified, the next verdict is `HOLD` or
`REBIND_REQUIRED`. No partial authorisation is possible.

## What "verified link" means

A `ChainedReceipt` must:

1. Reference the previous receipt's canonical hash via `prev_receipt_hash`.
2. Carry a strict-monotonic `sequence` number (`prev.sequence + 1`).
3. Reproduce the prior receipt's canonical hash exactly when recomputed.
4. Pass replay against the chain head — the head's `head_hash` must match
   the canonical hash of its receipt.

If any check fails, the chain is broken at that point.

## Prior-state participation

The next admissibility decision is computed from the proposed action plus
the output of a deterministic projector over the current chain.

The projector reads only fields that are explicitly modelled (see
`prior-state-projector.md`):

- recent refusal receipts within a fixed window
- unresolved `REBIND_REQUIRED` markers
- replay-attempt counters
- chain integrity status

Anything not in the schema does not participate in the decision.

## Evaluation order

`STRUCTURE_FIRST` then `FIRST_FAIL`.

1. Validate chain structure (linkage, sequence, head hash).
2. Evaluate prior-state projector.
3. Evaluate proposed action against projected state.
4. Stop at the first violation. Do not accumulate partial passes.

## Invariant status

`FROZEN` for v0.1. Not subject to PROJECT-level override.
