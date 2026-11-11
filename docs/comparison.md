# Comparison with adjacent systems

No standard in current use binds an AI decision to its inference-time reasoning in a way that makes post-hoc substitution detectable. Adjacent systems each solve a different part of the problem.

| | sovereign-record | Certificate Transparency / transparency logs | Sigstore | WORM storage / audit DBs | Blockchain anchoring |
|---|---|---|---|---|---|
| **Core idea** | Signed, chained records binding reasoning at inference time | Public append-only log of TLS certificates | Signing + transparency for software artifacts | Write-once storage for logs | Anchor chain heads on a distributed ledger |
| **Tamper evidence** | Yes (chain + signature) | Yes | Yes | Depends on product | Yes |
| **Reasoning binding** | `PRESENT`/`ABSENT` as signed first-class states | No | No | No | No (would wrap this, not replace it) |
| **Detects backdated time** | Yes (`monotonic_ns` ordering enforced) | N/A | N/A | No | Partially (block timestamps) |
| **Who can verify** | Anyone with the Ed25519 public key (or shared HMAC key) | Anyone | Anyone | Product users | Anyone |
| **Trusted third party** | External checkpoint custodian (optional, for rollback) | Log operators | Transparency log operators | Storage vendor | Consensus participants |
| **Runtime cost** | Microseconds per record (SHA-256 + one signature) | Heavy infrastructure | Heavy infrastructure | Licensing | On-chain fees |
| **Dependencies** | Python stdlib (+ optional `cryptography`) | Ecosystem-specific | Ecosystem-specific | Commercial | Chain integration |

## When this design is the right fit

- You need a minimal, auditable record of *what an AI system decided and whether it reasoned*, with cryptographic proof.
- You must run in constrained or offline environments (stdlib-only HMAC mode has zero dependencies).
- You need public verifiability without running infrastructure (Ed25519 + a published public key).

## When something else fits better

- **Software supply chain signing** → Sigstore.
- **Certificate issuance auditing** → Certificate Transparency.
- **Global tamper-proof ordering without a trusted party** → blockchain anchoring (this library's `export_anchor()` checkpoint is deliberately simple to anchor on-chain, but the library does not do it for you).
- **Long-term secret storage and access control** → a KMS/HSM plus a WORM store; use this library for the record structure, not for key management.

## Relation to the paper

`paper.md` develops the failure mode this design answers: audit systems check consistency, not contemporaneity, so post-hoc rationalizations pass audit. The record structure makes substitution detectable — its stated boundary is that it proves what was signed, not that the signer was truthful.
