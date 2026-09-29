# Post-hoc Rationalization in Clinical AI Audit Logs: A Record Structure That Makes Substitution Detectable

**Author:** onlyusemore
**Repository:** https://github.com/onlyusemore/sovereign-record
**License:** MIT

---

## Abstract

Clinical AI systems increasingly log decisions for audit. When a clinician asks why a recommendation was made, many systems generate an explanation after the fact, from a different process than the one that produced the decision. These post-hoc explanations are ingested into audit logs as if they were causal records. They pass audit because audit checks that logs exist and are internally consistent, not that they were written at the time of the decision. We describe this failure mode and propose a record structure in which reasoning is captured at inference or explicitly marked absent. Records are signed, chained, and monotonically sequenced; substitution is detectable, and absence is a first-class signed state. We state the boundary of the claim plainly: the ledger proves what was signed, not that the signer was truthful. We provide a reference implementation with five adversarial tests, and a threat model covering tampering, truncation, reordering, and insertion, and we enumerate what the structure does not protect against.

**Keywords:** provenance, auditability, clinical AI, post-hoc explanation, cryptographic logging

---

## 1. Introduction

In clinical AI deployments, an explanation of a model's decision often carries the same evidentiary weight as the decision itself. When a clinician asks why a recommendation was made, the answer is recorded, and that answer becomes part of the patient's record and the system's audit trail.

The problem is that the answer is frequently generated after the decision, by a process distinct from the one that produced the decision. The model may have emitted a recommendation with no legible reasoning path; a second system then produces a plausible rationale. The rationale reads well. It may be accurate. But it is not the cause of the decision, and it is not contemporaneous with it.

Audit systems typically verify that a log entry exists, that required fields are present, and that the log is internally consistent. They do not verify that the explanation was written at the time of the decision, by the process that made the decision. A post-hoc rationale satisfies all three checks. It therefore passes audit. The audit's correctness guarantee is weaker than it appears.

This paper makes three contributions:

1. It describes the failure mode precisely: explanations that are ingested as causes but are not contemporaneous with the decision.
2. It proposes a record structure in which reasoning is bound to the record at write time, and absence of reasoning is an explicit, signed state rather than a missing field.
3. It provides a threat model and a reference implementation with a reproducible adversarial test suite, including an explicit enumeration of what the structure does not protect against.

The boundary of the contribution is stated in the abstract and developed in Section 6: the structure makes substitution detectable. It does not make the signer truthful.

---

## 2. Background and Related Work

Several standards and systems address adjacent problems. None of them fills the gap this paper describes.

OAuth 2.0 Token Revocation (RFC 7009) defines how a client requests that a token be revoked, and how a server acknowledges the request. It is about revocation signaling, not about binding a token to the reasoning that produced its issuance.

Sigstore provides signing and transparency for software artifacts. It binds an identity to a build artifact and records the binding in a transparency log. It does not address inference-time reasoning or the problem of post-hoc explanation substitution.

Certificate Transparency (RFC 6962) and transparency logs more generally provide append-only, tamper-evident records. They are the right primitive for the chain structure proposed here, but the logs do not, by themselves, constrain what is written into them. A system that writes post-hoc rationales into a transparency log produces a tamper-evident record of a substituted explanation.

Work on chain-of-thought faithfulness has established that a model's stated reasoning may not reflect its internal computation. This paper is adjacent but distinct: the concern here is not whether the reasoning is faithful to the model's internals, but whether the record presented as reasoning was written at the time of the decision at all.

Clinical AI audit requirements under the FDA's guidance and the EU AI Act require that decisions be logged and explainable. They do not, as written, require that the explanation be contemporaneous with the decision. A system that generates explanations post-hoc can meet the letter of these requirements while violating their intent.

**The gap:** no standard or system in current use binds a decision to its reasoning in a way that makes post-hoc substitution detectable in a clinical audit context.

---

## 3. The Record Structure

We propose a record structure with three properties.

### 3.1 Inference-time binding

A record is written at the time of the decision. Its fields include:

- `seq`: a non-negative integer, gap-free from 0
- `token`: an identifier for the decision context
- `output`: the decision or recommendation
- `reasoning_state`: either `PRESENT` or `ABSENT`
- `reasoning`: a tuple of steps, empty iff `reasoning_state == ABSENT`
- `monotonic_ns`: the writer's monotonic clock reading at write time
- `wall_time_s`: an informational timestamp, signed but not trusted for ordering
- `prev_chain`: the previous record's chain head
- `signature`: an HMAC over the canonical payload

The invariant is enforced at construction: a `PRESENT` record must contain at least one step; an `ABSENT` record must contain none. `ABSENT` is a signed assertion that no reasoning was available. It is not a missing field. It is not an error. It is a first-class state that the writer cannot later replace with a fabricated rationale without breaking the signature.

### 3.2 Chain immutability

Each record's HMAC covers a chain hash over the previous record's canonical payload:

```
chain_0 = SHA256(0x00 * 32 || canonical(record_0))
chain_n = SHA256(chain_{n-1} || canonical(record_n))
```

The chain head is stored separately and atomically. On reload, every signature is re-derived, every chain link is re-computed, and the final state is compared against the anchor. Any edit, deletion, reordering, or insertion in the middle breaks the chain and is detected.

### 3.3 Monotonic sequencing

Records carry a gap-free sequence starting at 0. The anchor stores the expected count and chain head. If the record file is truncated or rolled back without also rewriting the anchor consistently, reload fails closed. The failure is deliberate: a tail truncation and a crashed append are indistinguishable from the record file alone, so the system refuses to guess and requires human intervention.

### 3.4 Reference implementation

The reference implementation is approximately 220 lines of Python, using only the standard library (`hmac`, `hashlib`, `json`, `os`, `time`, `pathlib`, `dataclasses`, `typing`). It includes a file-backed store with `fsync` on record append and atomic `os.replace` on the anchor, followed by a parent-directory `fsync` to make the rename durable.

The full source is available at https://github.com/onlyusemore/sovereign-record under the MIT License. See Section 3.5 for the full reproducibility record.

### 3.5 Reproducibility

The reference implementation and its adversarial test suite are publicly available at https://github.com/onlyusemore/sovereign-record.

The implementation is a single file, `sovereign_record.py`, comprising approximately 220 lines of Python, using only the standard library. It was executed and verified on Python 3.13.

The adversarial test suite, `test_adversarial.py`, comprises five tests. Each test constructs a ledger, applies a specific attack, and asserts that the attack is detected:

- `test_happy_path_and_reload` — verifies a pristine ledger across a reload
- `test_attack_tamper` — modifies a field after signing
- `test_attack_truncate` — removes the last record
- `test_attack_reorder` — swaps two records
- `test_attack_insert` — inserts a forged record in the middle

All five tests pass in 0.04 seconds on the reference environment. The test suite was independently cloned and executed by a third party outside the author's environment; the result was identical (`5 passed`).

To reproduce:

```
git clone https://github.com/onlyusemore/sovereign-record
cd sovereign-record
pip install pytest
python -m pytest test_adversarial.py -v
```

The cryptographic primitives are fixed and explicit:

- Chain hash: SHA-256 over `prev_chain || canonical(record)`
- Record signature: HMAC-SHA256 over `canonical(record)`
- Canonical form: JSON with `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`
- Key length: minimum 32 bytes, enforced at construction

The ledger fails closed on any detected inconsistency. A malformed line in the record file, a signature mismatch, a chain break, or an anchor count mismatch all raise typed exceptions (`PersistenceError`, `VerificationError`, `SequenceError`), and the ledger refuses to load. The system does not attempt to repair or guess.

---

## 4. Threat Model

The structure is designed to detect the following:

- **Content substitution.** Editing a record's output, reasoning, or reasoning_state after signing. Detected by signature verification.
- **Deletion in the middle.** Removing a record from an interior position. Detected by chain break.
- **Reordering.** Changing the order of records. Detected by chain break.
- **Insertion.** Adding a forged record between existing records. Detected by signature verification and chain break.
- **Tail truncation.** Removing the most recent records without updating the anchor. Detected by anchor count mismatch.
- **Rollback of the record file without the anchor.** Detected by anchor count mismatch.

The structure does not protect against:

- **Key compromise.** An attacker with the HMAC key can forge any record. The key must be held in a KMS or HSM, not in the writer's process memory.
- **Coordinated rollback.** An attacker who can rewrite both the record file and the anchor to a prior consistent state can produce a ledger that verifies. The only defense is external anchoring: publishing the chain head to an append-only log outside the writer's control.
- **Crash between record fsync and anchor replace.** On reload, the count will exceed the anchor and the ledger fails closed. Recovery is a human decision; the code does not guess.
- **Signer dishonesty.** A writer with the key can sign `ABSENT` when reasoning existed, or sign a fabricated rationale as `PRESENT`. The ledger proves what was signed. It does not prove that the signer was truthful at signing time.
- **Wall clock skew.** `monotonic_ns` is the ordering primitive. `wall_time_s` is informational and signed, so tampering is detectable, but it is not trustworthy for ordering.

---

## 5. Discussion: Why Institutions Prefer Ambiguous Records

Post-hoc rationalization passes audit because audit verifies consistency, not contemporaneity. A log entry that is internally consistent, present, and correctly formatted satisfies the checks that most audit systems perform. The question of when the entry was written, and by which process, is not asked.

This is not primarily a moral failure of the people who build these systems. It is a structural incentive. A contemporaneous record that captures the model's actual reasoning — including its absence — is a definitive artifact. In a litigation context, a definitive artifact concentrates liability on the party that produced it. An ambiguous record distributes liability. Organizations that optimize for liability distribution will therefore prefer the ambiguous record, even when the contemporaneous record is technically superior.

The contribution of this paper is not to resolve that incentive. It is to make the substitution detectable, so that the choice between definitive and ambiguous records is visible rather than implicit. A system that signs `ABSENT` when no reasoning existed has made a choice that can be audited. A system that generates a plausible rationale after the fact has made a choice that cannot.

---

## 6. Limitations and Open Problems

**The signer is not verified.** The ledger proves what was signed, not that the signer was honest. A writer with the key can lie. This is the fundamental boundary of the contribution.

**No independent security audit.** The implementation has been tested against the four attacks enumerated in Section 3.5. It has not been reviewed by a professional cryptographer. The use of HMAC-SHA256 and SHA-256 follows standard practice, but this is not a substitute for expert review. Production deployment should be preceded by such review.

**External anchoring is required for full rollback protection.** The structure described here detects tail truncation and rollback only against an anchor the writer controls. To defeat coordinated rollback, the anchor's chain head must be published to an append-only external log on a schedule. This is not implemented in the reference code.

**Key management is out of scope.** The reference implementation holds the key in process memory. Production use requires a KMS or HSM.

**The structure is not a substitute for faithful chain-of-thought.** A record with `reasoning_state == PRESENT` may still contain a rationale that does not reflect the model's internal computation. The structure makes substitution detectable; it does not make the reasoning faithful.

**Clinical deployment details are withheld.** The motivating deployment is described in this paper at the level of pattern, not specifics. Institution, dates, and location are omitted.

**Open problems.**

1. How to anchor chain heads externally without introducing a new trusted party.
2. How to bind a record to a specific model version and inference context in a way that is stable across model updates.
3. How to handle revocation of a record's authority without invalidating the chain.
4. How to specify audit requirements that distinguish contemporaneous from post-hoc records.

---

## 7. Conclusion

Post-hoc rationalization passes clinical audit because audit checks consistency, not contemporaneity. We have proposed a record structure in which reasoning is captured at inference or explicitly marked absent, signed, chained, and monotonically sequenced. Substitution is detectable; absence is a first-class state. The boundary is stated plainly: the ledger proves what was signed, not that the signer was truthful. The structure is a primitive, not a solution. It makes a choice visible. Whether that visibility changes practice is an open question.

---

## References

- RFC 6749, The OAuth 2.0 Authorization Framework
- RFC 7009, OAuth 2.0 Token Revocation
- RFC 6962, Certificate Transparency
- Sigstore, Software Signing and Transparency
- Wei et al., Chain-of-Thought Prompting Elicits Reasoning in Large Language Models, NeurIPS 2022
- FDA, Marketing Submission Recommendations for AI-Enabled Device Software Functions
- EU AI Act, Regulation (EU) 2024/1689
