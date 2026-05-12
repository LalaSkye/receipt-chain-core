# Commit Gate Integration Sketch v0.1

**Status:** DESIGN_SKETCH / NON_EXEC  
**Scope:** Demonstrated integration shape only  
**Claim:** A receipt-chain verdict can act as an input to a later commit-boundary decision.

---

## Purpose

`receipt-chain-core` demonstrates the temporal primitive:

```text
prior receipt state → next admissibility verdict
```

`commit-gate-core` demonstrates the path-local commit primitive:

```text
DecisionRecord → commit gate → mutation allowed/refused → receipt
```

This sketch shows the intended connection between the two primitives without claiming production integration.

---

## Integration shape

```text
Receipt chain
  ↓
Projected prior state
  ↓
Receipt-chain verdict
  ↓
Commit-boundary request
  ↓
Commit gate evaluates DecisionRecord
  ↓
ALLOW / HOLD / DENY
  ↓
Commit receipt or refusal receipt
```

---

## Minimal bridge rule

A commit-boundary request may proceed only if the receipt-chain layer returns a non-blocking verdict for the proposed action.

```text
receipt-chain verdict = ALLOW
→ commit gate may evaluate DecisionRecord

receipt-chain verdict = HOLD / DENY / REBIND_REQUIRED
→ commit gate must not create an executable mutation path
```

The receipt-chain layer does not execute.

The receipt-chain layer does not bind consequence.

It supplies prior-state evidence to the commit boundary.

---

## Example path: recent refusal blocks later commit

### Prior state

A prior receipt records a refusal for the same object.

```text
prior receipt verdict: HOLD
reason_code: upstream.refusal
object_id: msg-A
```

### Later proposed action

```text
action_type: send_email
object_id: msg-A
```

### Receipt-chain evaluation

```text
verdict: HOLD
reason_code: chain.recent_refusal_in_window
```

### Commit-boundary effect

The commit gate is not asked to create an executable mutation path.

Expected external result:

```text
mutation_performed: false
commit_gate_evaluated: false
reason: prior receipt state blocked continuation
```

---

## Example path: clean chain permits commit-gate evaluation

### Prior state

No blocking prior receipt state exists.

### Receipt-chain evaluation

```text
verdict: ALLOW
reason_code: chain.clean_no_blocking_state
```

### Commit-boundary effect

The proposed action may be passed to `commit-gate-core` for its own independent checks:

```text
DecisionRecord signature
scope
expiry
replay
receipt sink
```

If those checks fail, the commit gate still returns `HOLD` or `DENY` and writes a refusal receipt on the demonstrated path.

---

## Non-claim boundary

This sketch does not prove:

- production integration
- path-universal routing
- atomic commit
- payload binding
- side-effect enforcement
- deployment architecture
- enterprise governance
- legal compliance

It defines one intended bridge:

```text
receipt-chain state can become an input to a later commit-boundary decision.
```

---

## Next executable build

The next hardening step is a small runnable bridge demo:

```text
examples/commit_gate_bridge_demo.py
```

It should show:

1. receipt-chain `ALLOW` permits commit-gate evaluation
2. receipt-chain `HOLD` blocks commit-gate evaluation before mutation
3. commit-gate `HOLD` still refuses mutation if DecisionRecord is invalid
4. all outcomes remain receipt-visible

---

## Clean claim

```text
Yesterday's receipt can decide whether today's commit gate is even reached.
```

The commit gate remains the execution boundary.

The receipt chain supplies temporal admissibility state.
