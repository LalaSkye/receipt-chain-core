# Enterprise Scenario Matrix v0.1

**Status:** PUBLIC_DEMO_MATRIX / NON_EXEC  
**Scope:** Demonstrated paths only  
**Claim:** The receipt-chain → commit-boundary reachability pattern can be demonstrated across multiple enterprise-shaped consequence classes.

---

## Purpose

This matrix widens the bridge demo without widening the claim beyond the evidence.

It shows the same bounded control pattern across three enterprise-shaped action classes:

```text
prior receipt state
→ receipt-chain verdict
→ commit boundary reached or not reached
→ mutation true or false
→ reason visible
```

---

## Scenario classes

| Class | Action type | Consequence shape |
|---|---|---|
| External communication | `send_email` | External message could leave the system |
| Access control | `grant_access` | Privilege could change |
| Financial operation | `approve_payment` | Payment approval could bind |

---

## What a reviewer can run

```bash
python examples/enterprise_scenario_matrix_demo.py
```

Expected final line:

```text
ALL ENTERPRISE SCENARIOS PRODUCED EXPECTED RESULTS
```

---

## Demonstrated pattern

For each action class, the demo shows two paths.

### Path A — prior refusal blocks before commit gate

```text
prior receipt verdict: HOLD
same object attempted again
receipt-chain verdict: HOLD
commit_gate_reached: false
mutation_performed: false
```

### Path B — clean chain permits commit-gate evaluation

```text
receipt-chain verdict: ALLOW
valid local authority record: present
commit_gate_reached: true
commit_gate_code: ALLOW
mutation_performed: true
```

---

## Matrix

| Action type | Prior refusal path | Clean authority path |
|---|---|---|
| `send_email` | blocks before gate | reaches gate and mutates |
| `grant_access` | blocks before gate | reaches gate and mutates |
| `approve_payment` | blocks before gate | reaches gate and mutates |

---

## What this proves

This demo shows, on the demonstrated paths only:

- receipt-chain state can block later continuation before a commit boundary is reached
- a clean receipt-chain state can permit commit-boundary evaluation
- the same pattern can be demonstrated across multiple enterprise-shaped consequence classes
- mutation remains false when the receipt chain blocks the path
- mutation becomes true only on the clean-chain plus valid-authority path inside the local demo adapter

---

## What this does not prove

This demo does not prove:

- production deployment
- enterprise adoption
- regulatory compliance
- path-universal routing
- external side-effect enforcement
- real email delivery prevention
- real access-control integration
- real payment-system integration
- atomic commit
- payload binding
- production integration with `commit-gate-core`

---

## Claim boundary

The correct claim is:

```text
The same receipt-chain reachability pattern is demonstrated across three enterprise-shaped action classes.
```

The incorrect claim would be:

```text
This repo provides enterprise governance enforcement.
```

That broader claim is not made here.

---

## Clean line

```text
Wider corridors. Same narrow proof.
```
