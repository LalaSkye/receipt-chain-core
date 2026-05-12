# Receipt Chain Proof Pack v0.1 — Demonstrated Path

**Status:** PUBLIC_PROOF_ARTIFACT / NON_EXEC  
**Scope:** Demonstrated path only  
**Claim:** Prior receipt state can change the next admissibility verdict.

---

## Proof condition

This repository demonstrates one bounded temporal primitive:

```text
same chain + same head + same proposed action
→ deterministic verdict
→ chained receipt
→ replayable hash state
```

A receipt is not merely a log entry.

A receipt becomes part of the next decision surface.

---

## What a reviewer can run

```bash
python run_demo.py
python -m pytest -q
python scripts/verify_chain_invariants.py
```

Expected demo result:

```text
ALL DEMO SCENARIOS PRODUCED EXPECTED VERDICTS
```

---

## Demonstrated paths

### 1. Clean chain

A valid proposed action against an empty or valid chain produces:

```text
ALLOW
```

### 2. Recent refusal blocks continuation

A recent prior refusal for the same object changes the next verdict to:

```text
HOLD
```

Reason:

```text
chain.recent_refusal_in_window
```

### 3. Unresolved rebind blocks continuation

An unresolved `REBIND_REQUIRED` in the chain blocks the next non-rebind action.

Verdict:

```text
REBIND_REQUIRED
```

Reason:

```text
chain.unresolved_rebind
```

### 4. Rebind clears the block

A valid `rebind` receipt allows later evaluation to continue.

Verdict:

```text
ALLOW
```

### 5. Tampering breaks the chain

Changing a prior receipt invalidates the chain.

Verdict:

```text
HOLD
```

Reason:

```text
chain.tamper_detected
```

### 6. Replay suppression activates

Repeated matching attempts above threshold are suppressed.

Verdict:

```text
HOLD
```

Reason:

```text
chain.replay_suppressed
```

### 7. Refusal receipt hash mismatch is caught

A projected refusal receipt passes shape validation, then fails hash verification after mutation.

Reason:

```text
refusal_receipt.hash_mismatch_caught
```

---

## Receipt fields shown

Each `ChainedReceipt` carries:

```text
schema
projector_schema
sequence
prev_receipt_hash
decision_id
proposed_action
verdict
reason_code
reason
issued_at
does_not_execute
does_not_bind_consequence
receipt_hash
```

---

## What this proves

This proof pack shows:

- receipts are chained
- prior receipt state changes later verdicts
- broken sequence, link, or hash fails closed
- unresolved rebind blocks continuation
- recent refusal blocks continuation
- replay suppression can alter today's verdict
- refusal receipt mutation is detected by hash verification
- replay is deterministic on the demonstrated path

---

## What this does not prove

This repository does not prove:

- production deployment
- legal compliance
- certification
- standardisation
- universal path coverage
- atomic commit
- payload binding
- side-effect enforcement
- enterprise adoption

It does not execute mutation.

It does not bind consequence.

It demonstrates the receipt-chain primitive that can feed a commit boundary.

---

## Clean claim

```text
Yesterday's receipt changes today's door.
```

A reviewer can run the demo and inspect where the door changes.
