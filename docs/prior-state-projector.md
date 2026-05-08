# Prior-State Projector v0.1

## Purpose

The projector is the deterministic function that turns a chain of receipts
into the input the next admissibility decision actually reads.

It is the only path by which prior chain state can influence today's
verdict. Anything not exposed by the projector cannot change the verdict.

## Schema version

`receipt_chain_core.projector.v0.1`

The schema version is recorded in every receipt produced under this
projector. Changing the schema requires bumping the version and is not a
silent change.

## What the projector reads

For projector v0.1, the projected state object has exactly these fields:

| Field | Type | Meaning |
|---|---|---|
| `chain_status` | enum (`OK`, `BROKEN_LINK`, `BROKEN_SEQUENCE`, `BROKEN_HASH`, `EMPTY`) | result of running the chain verifier |
| `head_sequence` | integer or null | sequence number of the most recent receipt, or null if empty |
| `recent_refusal` | object or null | most recent receipt within the refusal window whose verdict was `DENY` or `HOLD` for the same `action_type` and `object_id`, otherwise null |
| `unresolved_rebind` | bool | true if the chain contains a `REBIND_REQUIRED` receipt that has not been followed by a rebind receipt for the same `object_id` |
| `replay_attempt_count` | integer | number of receipts in the refusal window with the same `proposed_action` canonical hash as the new proposal |

Nothing else. If a future version reads more, it requires a schema bump.

## The refusal window

The refusal window is fixed at v0.1 to **the last 5 receipts**.

The window is intentionally small. v0.1 is a primitive, not a policy
engine. A larger or time-based window is a future-version decision.

## Rebind receipts

A rebind receipt is any chained receipt whose `proposed_action.action_type`
is `"rebind"` and whose `verdict` is `ALLOW`. It must reference the same
`object_id` as the unresolved `REBIND_REQUIRED` it intends to clear.

When such a rebind receipt appears later in the chain than the unresolved
`REBIND_REQUIRED` for the same `object_id`, `unresolved_rebind` is `false`.

## How the verdict uses the projection

For a proposed action `A` and projected state `P`, the verdict is:

| Condition | Verdict | Reason code |
|---|---|---|
| `P.chain_status != OK` | `HOLD` | `chain.tamper_detected` |
| `P.unresolved_rebind == true` and `A.action_type != "rebind"` | `REBIND_REQUIRED` | `chain.unresolved_rebind` |
| `P.recent_refusal != null` | `HOLD` | `chain.recent_refusal_in_window` |
| otherwise | `ALLOW` | `chain.clean_no_blocking_state` |

This is intentionally a small ladder. It does not implement policy. It
implements one thing: prior chain state participating in the next
admissibility decision.

## Determinism

Given the same chain bytes and the same proposed action bytes, the
projector returns identical state. Replay is therefore deterministic.

## Out of scope (v0.1)

- time-based windows
- weighted recency
- partial-credit overrides
- multi-tenant scoping beyond `object_id`
- any policy beyond the four-row ladder above
- any field not in the projected-state schema
