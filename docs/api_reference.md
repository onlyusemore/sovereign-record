# API reference

Single module: `sovereign_record`. HMAC mode needs only the Python standard library; Ed25519 mode needs the optional `cryptography` package.

## Data classes

### `Step`
```python
Step(source: str, content: str)
```
A signed reasoning step. Immutable dataclass.

### `Record`
```python
Record(seq, token, output, reasoning_state, reasoning, monotonic_ns,
       wall_time_s, prev_chain, signature="")
```
Immutable, signed ledger entry. Fields:

| Field | Meaning |
|---|---|
| `seq` | Gap-free record number starting at 0 |
| `token` | Identifier for the decision context |
| `output` | The decision or recommendation |
| `reasoning_state` | `"PRESENT"` or `"ABSENT"` (enforced) |
| `reasoning` | Tuple of `Step`; non-empty iff `PRESENT` (enforced) |
| `monotonic_ns` | Writer's monotonic clock at write time; must never go backwards |
| `wall_time_s` | Informational timestamp; signed, not used for ordering |
| `prev_chain` | Previous record's chain head (hex) |
| `signature` | Hex-encoded HMAC-SHA256 or Ed25519 signature |

Validation in `__post_init__` (raises `TypeError` / `ValueError`):
- `reasoning_state` must be a string equal to `PRESENT` or `ABSENT`
- `ABSENT` records must have empty `reasoning`; `PRESENT` must have ≥ 1 step
- every `reasoning` entry must be a `Step`

Methods: `payload_for_signing() -> dict`.

## Signers

### `HmacSigner`
```python
HmacSigner(key: bytes)          # key >= 32 bytes, enforced
.sign(msg: bytes) -> str        # hex HMAC-SHA256
.verify(msg: bytes, sig: str) -> bool
```
Symmetric: writer and verifier share the key.

### `Ed25519Signer`
```python
Ed25519Signer.generate() -> Ed25519Signer
Ed25519Signer.from_private_hex(hex) -> Ed25519Signer   # writer
Ed25519Signer.from_public_hex(hex) -> Ed25519Signer    # verify-only
.public_key_hex() -> str
.private_key_hex() -> str
.sign(msg: bytes) -> str        # TypeError if verify-only
.verify(msg: bytes, sig: str) -> bool
```
Asymmetric: private key writes; public key verifies and cannot write. Requires `cryptography`; raises `RuntimeError` at construction if it is missing.

## `Ledger`

```python
Ledger(key=None, *, signer=None, storage_path=None,
       time_fn=time.monotonic_ns, wall_fn=time.time)
```

Pass exactly one of `key=` (HmacSigner, default) or `signer=`. If `storage_path` is given, the ledger loads and persists to disk.

### Writing
```python
append(token: str, output: str, reasoning: list[Step] | None = None) -> Record
```
Determines `reasoning_state` automatically (`PRESENT` iff steps are given), refuses to create a record whose `monotonic_ns` is older than the last record's (`SequenceError`), signs, persists (`fsync` + atomic anchor replace), and returns the signed record.

### Verifying
```python
verify(external_anchor: Mapping | None = None) -> None
```
Re-derives every signature, chain link, and sequence number; enforces non-decreasing `monotonic_ns`; checks the on-disk anchor; and, if `external_anchor={"count": int, "chain": hex}` is supplied, requires an exact match. Raises `VerificationError`, `SequenceError`, or `PersistenceError` on any inconsistency (fails closed).

```python
export_anchor() -> dict   # {"count": N, "chain": "<hex>"} after self-verify
```

## Exceptions

`LedgerError` (base) · `VerificationError` · `SequenceError` · `PersistenceError` — all raised instead of silent repair.

## CLI

```bash
python sovereign_record.py keygen [--scheme ed25519|hmac]
python sovereign_record.py init DIRECTORY
python sovereign_record.py append DIRECTORY TOKEN OUTPUT [--reasoning FILE] [--json]
python sovereign_record.py verify DIRECTORY [--external-anchor FILE] [--json]
python sovereign_record.py export-anchor DIRECTORY
```

Keys come from environment variables, never argv:

| Variable | Role |
|---|---|
| `SOVEREIGN_RECORD_KEY_HEX` | HMAC secret key (write + verify) |
| `SOVEREIGN_RECORD_PRIVATE_KEY_HEX` | Ed25519 private key (write) |
| `SOVEREIGN_RECORD_PUBLIC_KEY_HEX` | Ed25519 public key (verify only) |

Exit codes: `0` success · `1` verification/append failure · `2` usage error.
`--json` emits machine-readable output; failures print `{"status": "failed", "error": ...}` to stderr.

## Test suite

`python -m pytest -q` — 39 tests across five files: adversarial chain attacks (6), reasoning-state validation (10), monotonic-time ordering (6), Ed25519 signing (10), CLI (7).
