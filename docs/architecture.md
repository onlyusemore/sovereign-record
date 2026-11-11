# Architecture

`sovereign-record` is a signed, append-only record ledger. It is deliberately small: one Python module, two on-disk artifacts per ledger, and a chain of SHA-256 hashes sealed by either HMAC-SHA256 or Ed25519 signatures.

## Components

```
┌──────────────┐      ┌───────────────────────────────────────┐
│ Writer (AI   │      │ Ledger directory (one per use case)  │
│ system /     │      │                                       │
│ agent)       │      │  records.jsonl   append-only, fsync   │
│              │      │  anchor.json      atomic replace      │
│ holds:       ├─────▶│                                       │
│  HMAC key or │      │  seq 0 ──▶ seq 1 ──▶ seq 2 ──▶ ...   │
│  Ed25519     │      │  each record signs its payload AND    │
│  private key │      │  the previous record's chain head     │
└──────────────┘      └───────────────────────────────────────┘
                                   │
                                   │ export_anchor()
                                   ▼
                       ┌───────────────────────┐
                       │ External checkpoint    │
                       │ {"count", "chain"}     │
                       │ stored OUTSIDE the      │
                       │ writer's control        │
                       └───────────────────────┘
                                   ▲
                                   │ verify(external_anchor=...)
┌──────────────┐                   │
│ Any auditor  ├───────────────────┘
│ with the     │      ┌───────────────────────────────────────┐
│ PUBLIC key   │      │ In-memory verification re-derives:    │
│ (Ed25519) or │      │  seq gap-freeness, chain links,       │
│ shared HMAC  │      │  every signature, monotonic_ns order, │
│ key          │      │  and the on-disk anchor               │
└──────────────┘      └───────────────────────────────────────┘
```

## The chain

Each record stores its canonical payload (JSON, sorted keys, no spaces) plus `prev_chain`, the previous record's chain head. The chain head is computed as:

```
chain_0 = SHA256(0x00 * 32 || canonical(record_0))
chain_n = SHA256(chain_{n-1} || canonical(record_n))
```

The record's signature (HMAC-SHA256 or Ed25519) covers the canonical payload, which includes `prev_chain`. Editing any field of any record breaks its signature; removing, reordering, or inserting records breaks chain links and sequence numbers.

## The anchor

`anchor.json` stores `{"count": N, "chain": <head>}` and is rewritten atomically (`os.replace` + directory `fsync`) after each append. On reload the ledger fails closed unless the on-disk records exactly match the anchor — truncation and rollback cannot pass local verification. Because a coordinated attacker can rewrite both files, full rollback protection additionally requires an externally retained checkpoint (see below).

## Signers

Two interchangeable signers implement `sign(msg) -> hex` and `verify(msg, sig) -> bool`:

- `HmacSigner` — symmetric, standard library only. Writer and verifier share the secret key.
- `Ed25519Signer` — asymmetric, optional `cryptography` dependency. The writer holds the private key; any holder of the 32-byte public key can verify but cannot append.

## Monotonic time

`monotonic_ns` is the ordering primitive (wall clock is informational only). `append()` refuses to create a record whose `monotonic_ns` is older than its predecessor's, and `verify()` plus on-disk reload reject backdated sequences even when the records are correctly signed and chained.

## Reasoning binding

`reasoning_state` must be exactly `PRESENT` (with at least one signed `Step`) or `ABSENT` (with none). `ABSENT` is a first-class signed assertion that no reasoning was available — it cannot later be replaced by a fabricated rationale without breaking the signature.

## External checkpoint

`export_anchor()` returns the verified `{count, chain}` snapshot. An auditor retains it outside the writer's control and passes it to `verify(external_anchor=...)`. The comparison is exact: the ledger must match the checkpoint's count and chain head. This is what detects coordinated rollback of both local files.

## What this is not

- Not a blockchain: no distributed consensus; trust concentrates in the key holder plus the external checkpoint custodian.
- Not a proof of signer honesty: the ledger proves what was signed, not that the signer was truthful.
- Not a timestamp authority: `wall_time_s` is informational; ordering comes from `monotonic_ns` and the sequence chain.
