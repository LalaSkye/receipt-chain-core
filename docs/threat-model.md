# Threat Model v0.1

## Scope

This threat model covers `receipt-chain-core` v0.1 only.

It addresses the demonstrated path: in-process evaluation of a chain of
receipts and a proposed action, producing a verdict and a new chained
receipt.

It does not cover storage, transport, key management, signature
verification, or downstream execution. Those are out of scope for v0.1 and
belong to deployment architecture.

## In-scope threats

### T1. Chain mutation
**Attacker action.** Modify any field of any past receipt to change what
the projector sees.

**Defence.** Each receipt carries `receipt_hash` over its canonical form.
The verifier recomputes the hash; mismatch returns `BROKEN_HASH`. On the
next-receipt path, `prev_receipt_hash` no longer matches the prior receipt
and the linkage returns `BROKEN_LINK`.

**Test.** `tests/test_tamper_detection.py::test_mutation_breaks_chain`.

### T2. Chain truncation
**Attacker action.** Drop one or more receipts from the middle or end of
the chain.

**Defence.** Sequence numbers are strict-monotonic from 0. Removal forces
either a `BROKEN_SEQUENCE` outcome or a `BROKEN_LINK` outcome at the next
receipt. The verifier rejects.

**Test.** `tests/test_tamper_detection.py::test_removal_breaks_chain`.

### T3. Chain reorder
**Attacker action.** Swap the position of two receipts.

**Defence.** Sequence numbers and `prev_receipt_hash` linkage both fail
on reorder. The verifier returns `BROKEN_LINK` and `BROKEN_SEQUENCE`.

**Test.** `tests/test_tamper_detection.py::test_reorder_breaks_chain`.

### T4. Replay through chain replacement
**Attacker action.** Substitute a different chain that ends in `ALLOW`
and re-issue the same proposed action to obtain `ALLOW`.

**Defence.** This v0.1 does not authenticate the chain — there is no
signature. A caller deciding to honour a different chain is a deployment
trust decision, not a defence inside this kernel.

**Status.** Out of scope for v0.1. Deferred to a future repo or to the
deployment architecture (see "Out of scope" below).

### T5. Verdict drift via projector schema change
**Attacker action.** Change the projector schema between calls so that the
same chain produces a different verdict.

**Defence.** The projector schema is versioned. Receipts record the
projector schema version they were evaluated under. A schema change is
visible in the chain and breaks deterministic replay if applied to old
receipts.

**Test.** `tests/test_prior_state_projector.py::test_projector_schema_recorded`.

### T6. Hash collision
**Attacker action.** Construct two receipts with the same canonical hash.

**Defence.** SHA-256 is treated as collision-resistant for v0.1. No
defence beyond the algorithm. If SHA-256 is broken, the whole chain
discipline must be rebuilt.

**Status.** Accepted residual risk for v0.1.

### T7. Missing required fields
**Attacker action.** Submit a structurally invalid receipt.

**Defence.** `STRUCTURE_FIRST` evaluation. Receipt construction validates
required fields; chain verification rejects malformed receipts before
running projector logic.

**Test.** `tests/test_chain_append_and_verify.py::test_malformed_receipt_rejected`.

## Out of scope (v0.1)

Explicitly out of scope. Adding any of these is a separate architectural
decision:

- cryptographic signing of receipts and authenticated chain authorship
- key management and rotation
- transport security
- distributed consensus over the chain
- storage durability and corruption-at-rest defences
- payload binding (deferred to `commit-gate-core` hardening issues)
- atomic commit boundary (deferred to `commit-gate-core` hardening issues)
- side-channel detection (retries, rollbacks, recovery flows, manual
  overrides, direct database writes)
- path-universal coverage of all routes that can reach mutation
- enforcement of downstream side-effects after a verdict is returned

A deployment that uses `receipt-chain-core` must address these
concerns at the architecture level. This kernel does not.

## Failure mode

If any in-scope defence fails, the verdict is `HOLD` or
`REBIND_REQUIRED`. The kernel never silently falls through to `ALLOW`
under verifier failure.
