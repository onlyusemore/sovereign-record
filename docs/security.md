# Security model

This document states what the ledger detects, what it cannot detect, and the operational requirements for each guarantee. It mirrors the threat model in the paper (`paper.md`, Section 4).

## Guarantees

| Attack | Detected by | Where |
|---|---|---|
| Edit a field after signing | Signature mismatch | `verify()`, reload |
| Delete a record in the middle | Chain break + seq gap | `verify()`, reload |
| Reorder records | Chain break + seq order | `verify()`, reload |
| Insert a forged record | Signature + chain break | `verify()`, reload |
| Tail truncation | Anchor count mismatch | reload |
| Rollback of records file only | Anchor count mismatch | reload |
| Backdated `monotonic_ns` (even correctly signed) | Monotonic-order check | `append()` refuses to write; `verify()` and reload reject |
| Coordinated rollback of both local files | **External checkpoint only** | `verify(external_anchor=...)` |
| Unknown / non-string `reasoning_state` | Construction-time validation | `Record.__post_init__` |
| `PRESENT` without steps, `ABSENT` with steps | Construction-time validation | `Record.__post_init__` |

## Non-goals (what this does NOT protect against)

- **Key compromise.** Whoever holds the HMAC key or the Ed25519 private key can forge any record. Hold keys in a KMS/HSM, never in committed files or argv.
- **Signer dishonesty at signing time.** A writer can sign `ABSENT` when reasoning existed, or sign a fabricated rationale as `PRESENT`. The ledger proves what was signed, not that the signer was truthful.
- **Coordinated rollback without an external checkpoint.** An attacker who rewrites both `records.jsonl` and `anchor.json` to a prior consistent state passes local verification. Only a checkpoint retained outside the attacker's control detects this.
- **Wall clock manipulation.** `wall_time_s` is informational and signed (tamper-detectable) but never used for ordering.
- **Compromise of the checkpoint store itself.** If the attacker controls the "external" checkpoint too, rollback protection is void.

## Key handling rules

1. Keys are supplied via environment variables, never command-line arguments: `SOVEREIGN_RECORD_KEY_HEX` (HMAC), `SOVEREIGN_RECORD_PRIVATE_KEY_HEX` / `SOVEREIGN_RECORD_PUBLIC_KEY_HEX` (Ed25519).
2. With Ed25519, verifiers need only the public key — publish it; keep the private key with the writer.
3. Rotate to a new ledger (not in-place re-signing) if a key is suspected compromised; re-signing history is exactly the attack this design exists to detect.
4. A `verify-only` Ed25519 signer raises `TypeError` on `append()` — public key holders cannot write.

## Cryptographic primitives

- Chain hash: SHA-256 over `prev_chain || canonical(record)`.
- Record signatures: HMAC-SHA256 (default, standard library) or Ed25519 (optional, `cryptography` package).
- Canonical form: JSON, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False`.
- HMAC keys: minimum 32 bytes, enforced at construction.
- Comparison uses constant-time checks where the primitive provides them (`hmac.compare_digest`, Ed25519 library verification).

## Operational requirements

- **Durability:** every append does `fsync` on the record file, atomic replace of the anchor, and a parent-directory `fsync`.
- **Fail-closed loading:** malformed lines, signature mismatches, chain breaks, anchor mismatches, and backdated time all raise typed exceptions and refuse to load. No repair, no guessing.
- **External checkpoint discipline:** export a checkpoint after writing, retain it in an independently controlled durable store, and verify against it during audits. Later legitimate appends require a newer checkpoint (the API verifies exact states, not historical prefixes).

## Known limitations

- No professional cryptographic review has been performed (see the paper's limitations section).
- Recovery from a crash between record `fsync` and anchor replace is a human decision; the ledger refuses to guess.
- The library exports and checks checkpoints; it does not publish them, prove their timestamps, or run an append-only service.
