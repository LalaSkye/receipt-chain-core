# Observation Condition Receipt

**Status:** `DRAFT / NON_EXEC / SPEC_SEED` — v0.1

A claim that observation preserved proof conditions is not itself proof.

The system must produce a receipt showing which observation conditions were checked, what boundary evaluated them, and whether the observation was permitted or refused.

---

## Purpose

This note defines a small receipt requirement for claims such as:

- observation preserved truth
- observation did not contaminate the state
- observation preserved continuity
- observation stayed inside lawful scope
- observation can be replayed

Those are valid proof-condition claims only if the system can show evidence that the conditions were enforced at the moment the observation became eligible to count as proof.

---

## Core distinction

| Claim layer | Receipt layer |
|---|---|
| Names proof conditions | Shows the condition check that occurred |
| Says observation was non-contaminating | Shows what boundary checked contamination risk |
| Says the record is replayable | Shows the replay path and chain reference |
| Says lawful scope was preserved | Shows the scope check and verdict |
| Says continuity held | Shows the prior and next chain state |

Naming the condition is not the same as proving the condition held.

---

## Minimum receipt fields

An `ObservationConditionReceipt` should record:

```json
{
  "receipt_type": "observation_condition_receipt",
  "observed_artifact_hash": "sha256:...",
  "observer_id": "observer-or-process-id",
  "boundary_id": "observation-boundary-id",
  "conditions_checked": [
    "truth_invariant",
    "non_contamination",
    "continuity",
    "lawful_scope",
    "replayability"
  ],
  "verdict": "ALLOW | HOLD | DENY",
  "reason_code": "observation.condition.pass_or_fail",
  "prior_chain_head": "sha256:...",
  "new_chain_head": "sha256:...",
  "replay_reference": "local-test-vector-or-verifier-id",
  "does_not_execute": true,
  "does_not_bind_consequence": true
}
```

---

## Verdict rule

If an observation cannot show its condition receipt, it may remain a note, log, measurement, or dashboard event.

It must not be promoted to proof.

```text
NO CONDITION RECEIPT -> NO PROOF PROMOTION
```

---

## Relation to receipt-chain-core

This document does not add a new runtime claim.

It extends the receipt-chain question to observation itself:

> If a future admissibility decision depends on an observation, the observation must carry a receipt proving why it was eligible to enter the chain.

---

## Claim boundary

This note does not prove:

- a full observation governance runtime
- production enforcement
- legal admissibility
- external framework failure
- universal coverage of proof conditions

It defines one bounded seed:

> Observation-condition claims need receipts before they can become proof claims.

---

## Clean line

Where is the receipt for the observation itself?
