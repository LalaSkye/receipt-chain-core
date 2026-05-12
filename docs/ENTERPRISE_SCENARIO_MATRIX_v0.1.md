# Enterprise-Shaped Scenario Matrix v0.1

**Status:** PUBLIC_DEMO_MATRIX / NON_EXEC  
**Scope:** Demonstrated paths only  
**Claim:** The receipt-chain → commit-boundary reachability pattern can be demonstrated across multiple enterprise-shaped consequence classes.

---

## Purpose

This matrix widens the bridge demo without widening the claim beyond the evidence.

It shows the same bounded local control pattern across three enterprise-shaped action classes:

```text
prior receipt state
→ receipt-chain verdict
→ local commit-boundary adapter reached or not reached
→ local demo mutation true or false
→ reason visible
```

The action classes are representative labels for common enterprise consequence shapes. They are not live integrations.

---

## Scenario classes

| Class | Action type | Consequence shape |
|---|---|---|
| External communication | `send_email` | Message could leave |
| Access control | `grant_access` | Privilege could change |
| Financial operation | `approve_payment` | Payment could bind |

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

For each enterprise-shaped action class, the demo shows two local paths.

### Path A — prior refusal blocks before local commit adapter

```text
prior receipt verdict: HOLD
same object attempted again
receipt-chain verdict: HOLD
commit_gate_reached: false
mutation_performed: false
```

### Path B — clean chain permits local commit-adapter evaluation

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
| `send_email` | blocks before adapter | reaches adapter |
| `grant_access` | blocks before adapter | reaches adapter |
| `approve_payment` | blocks before adapter | reaches adapter |

---

## What this proves

This demo shows, on the demonstrated paths only:

- receipt-chain state can block later continuation before a local commit-boundary adapter is reached
- a clean receipt-chain state can permit local commit-adapter evaluation
- the same reachability pattern can be demonstrated across multiple enterprise-shaped consequence classes
- local demo mutation remains false when the receipt chain blocks the path
- local demo mutation becomes true only on the clean-chain plus valid-authority path inside the local demo adapter

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

The demo does not send email, change access, approve payment, or touch external systems.

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
