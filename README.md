# receipt-chain-core

**Status:** `DRAFT / NON_EXEC / BUILD_NIGHT_CANDIDATE` — v0.1

Prior receipt state participates in the next admissibility decision.

> Yesterday's receipt changes today's door.

---

## What it is

`receipt-chain-core` is a minimal reference artifact for cross-decision
receipt chaining.

A receipt does not just describe what happened.

It becomes part of the input that decides what happens next.

This repo is a sibling to
[`commit-gate-core`](https://github.com/LalaSkye/commit-gate-core), which
demonstrates a single-call commit-boundary primitive. `receipt-chain-core`
demonstrates the **temporal** primitive: the link between yesterday's
verdict and today's verdict.

---

## Invariant v0.1

> A new admissibility decision is invalid unless it carries a verified link
> to the prior chain state.

If the link cannot be verified, today's verdict is `HOLD` or
`REBIND_REQUIRED`. No silent continuation.

Evaluation order is `STRUCTURE_FIRST` then `FIRST_FAIL`: validate structure
before evaluating claims, stop at the first violation.

The invariant is `FROZEN` for v0.1.

---

## What this proves

- Receipt N+1 cryptographically references Receipt N.
- Removing, reordering, or mutating any past receipt invalidates the chain.
- Today's verdict reads chain state as a deterministic input.
- A recent refusal in the chain can change today's verdict on the
  demonstrated path.
- An unresolved `REBIND_REQUIRED` in the chain blocks the next call until a
  rebind receipt is appended.
- Replay is deterministic: same chain + same head + same proposed action →
  same verdict.
- A high replay attempt count within the window can change today's verdict
  on the demonstrated path.

---

## What this does not prove

This repository does not prove:

- adoption
- certification
- production readiness
- standardisation
- legal compliance
- path-universal coverage
- payload binding
- atomic commit
- side-effect enforcement
- deployment
- evidence of field validation

It demonstrates one bounded primitive:

> Prior receipt state can affect the next admissibility decision.

---

## Position in the corpus

| Repo | Role |
|---|---|
| [`start-here`](https://github.com/LalaSkye/start-here) | Entry surface |
| [`commit-gate-core`](https://github.com/LalaSkye/commit-gate-core) | Path-local commit boundary |
| `receipt-chain-core` | Temporal receipt-chain primitive (this repo) |
| [`fail-closed-ai`](https://github.com/LalaSkye/fail-closed-ai) | Doctrine and corridor |
| NEO Guard (inside `fail-closed-ai`) | Human-node chain surface |

This repo closes the gap noted in `start-here` issue #1: cross-decision
hash chaining, with prior chain state as a deterministic input to the next
admissibility decision.

---

## Try it in 30 seconds

```bash
git clone https://github.com/LalaSkye/receipt-chain-core.git
cd receipt-chain-core
python run_demo.py
```

No dependencies beyond Python 3.9+. No install step.

Expected last lines:

```text
[5/5] tampered chain          -> HOLD              (chain.tamper_detected)
ALL DEMO SCENARIOS PRODUCED EXPECTED VERDICTS
```

---

## Proof pack

For a reviewer-facing walkthrough of the demonstrated receipt-chain paths, see:

[`docs/PROOF_PACK_v0.1.md`](docs/PROOF_PACK_v0.1.md)

It shows the bounded proof condition, runnable commands, demonstrated verdict
changes, receipt fields, and claim boundary.

---

## Run tests and verifier

```bash
python -m pytest -q
python scripts/verify_chain_invariants.py
```

Both must pass. The verifier writes
`tests/adversarial/latest_verification_receipt.json` as evidence.

---

## Verdict vocabulary

| Verdict | Meaning |
|---|---|
| `ALLOW` | Admissible. The next gate may evaluate. |
| `HOLD` | Cannot be validated under the current chain. Stop. |
| `DENY` | Invalid or prohibited. Stop. |
| `REBIND_REQUIRED` | Chain is structurally valid, but prior state requires a rebind receipt before continuing. |

Ambiguity is not permission.

---

## Core rule

A `ChainedReceipt` must:

- reference the previous receipt's canonical hash
- carry a strict-monotonic sequence number
- pass replay against the chain head
- expose its prior-state effects through a deterministic projector

If any check fails: `HOLD` or `REBIND_REQUIRED`.

Each receipt also declares:

```json
{
  "does_not_execute": true,
  "does_not_bind_consequence": true
}
```

This repo produces verdicts. It does not execute mutation. It does not bind
consequence. Both are deferred to `commit-gate-core` and to the deployment
architecture around it.

---

## Repository map

```text
receipt-chain-core/
├── README.md
├── LICENSE
├── docs/
│   ├── invariant.md
│   ├── threat-model.md
│   ├── chain-spec.md
│   ├── prior-state-projector.md
│   └── PROOF_PACK_v0.1.md
├── src/
│   └── receipt_chain_core/
│       ├── __init__.py
│       ├── chain.py
│       ├── receipt.py
│       ├── projector.py
│       ├── hashing.py
│       └── verdict.py
├── examples/
│   ├── 01_single_receipt.py
│   ├── 02_clean_chain_of_three.py
│   ├── 03_tamper_breaks_chain.py
│   ├── 04_recent_refusal_changes_verdict.py
│   └── 05_unresolved_rebind_blocks_next.py
├── tests/
│   ├── test_chain_append_and_verify.py
│   ├── test_tamper_detection.py
│   ├── test_prior_state_projector.py
│   ├── test_verdict_changes_under_chain_state.py
│   ├── test_replay_suppression.py
│   └── adversarial/
│       ├── INVARIANT_TEST_VECTORS_v1.json
│       └── test_invariants.py
├── scripts/
│   └── verify_chain_invariants.py
└── run_demo.py
```

---

## Claim boundary

This repo may claim only:

- receipts can be chained on the demonstrated path
- prior chain state can be read deterministically by the next admissibility
  decision
- tampering, removal, or reordering breaks chain verification
- a recent refusal or unresolved rebind can change today's verdict on the
  demonstrated path
- a high replay attempt count within the window can change today's verdict
  on the demonstrated path

This repo must not claim:

- adoption
- certification
- production readiness
- standardisation
- compliance
- universal path coverage
- payload binding
- atomic commit
- side-effect enforcement
- deployment
- evidence of field validation

Public claims must match what the tests prove. Nothing larger.

---

## Licence

MIT. Use it. Break it. Show the receipt.
