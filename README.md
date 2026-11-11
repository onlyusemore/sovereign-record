# sovereign-record

[![Tests](https://github.com/onlyusemore/sovereign-record/actions/workflows/tests.yml/badge.svg)](https://github.com/onlyusemore/sovereign-record/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/onlyusemore/sovereign-record)](https://github.com/onlyusemore/sovereign-record/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/onlyusemore/sovereign-record/actions/workflows/tests.yml)

A minimal reference implementation of a signed, append-only record ledger that binds AI reasoning to decisions at inference time — and makes post-hoc substitution detectable.

**Read the paper:** [`paper.md`](paper.md) — *Post-hoc Rationalization in Clinical AI Audit Logs*.

## Why

When a clinician, regulator, or engineer asks "why did the AI decide this?", most systems generate an explanation after the fact, from a different process than the one that produced the decision. Today's audits check that logs exist and are internally consistent — not that the explanation was written at the time of the decision. This library makes that substitution detectable:

- **Inference-time binding** — reasoning is signed at write time, or the record is marked `ABSENT`: a first-class signed state the writer cannot later replace with a fabricated rationale.
- **Chain immutability** — each record's signature (HMAC-SHA256 or Ed25519) covers the previous chain head; any edit, deletion, reorder, or insertion breaks the chain.
- **Monotonic sequencing** — gap-free record numbers anchored against truncation; `monotonic_ns` must never go backwards: `append()` refuses to write such a record and verification rejects any backdated sequence, even correctly signed ones.
- **Public verifiability** — with Ed25519, anyone holding the 32-byte public key can verify the entire ledger but cannot write to it.
- **External checkpoints** — a separately retained chain head detects coordinated rollback of both local files.

The boundary, stated plainly: **the ledger proves what was signed, not that the signer was truthful.**

## Install

```bash
git clone https://github.com/onlyusemore/sovereign-record
cd sovereign-record
python -m pip install cryptography   # optional — only needed for Ed25519
```

HMAC mode uses only the Python standard library. Requires Python 3.10+.

## Usage

Generate a keypair, write records, verify from outside:

```bash
python sovereign_record.py keygen --scheme ed25519
# {"scheme": "ed25519", "private_key_hex": "...", "public_key_hex": "..."}

export SOVEREIGN_RECORD_PRIVATE_KEY_HEX="<private_key_hex>"
python sovereign_record.py init my-ledger
python sovereign_record.py append my-ledger "case-42" "Recommend amoxicillin 500mg"
# appended seq=0 reasoning_state=ABSENT

python sovereign_record.py append my-ledger "case-43" "..." --reasoning steps.json
# appended seq=1 reasoning_state=PRESENT

# Any third party — public key only:
export SOVEREIGN_RECORD_PUBLIC_KEY_HEX="<public_key_hex>"
python sovereign_record.py verify my-ledger
# verified
```

Full walkthrough: [docs/quickstart.md](docs/quickstart.md) · CLI details: [docs/api_reference.md](docs/api_reference.md).

### Python API

```python
from sovereign_record import Ed25519Signer, Ledger, Step

signer = Ed25519Signer.generate()
public_hex = signer.public_key_hex()                       # publish this
led = Ledger(signer=signer, storage_path="my-ledger")
led.append("case-1", "output",
           reasoning=[Step(source="model", content="...")])
led.verify()

# Any third party, public key only — can verify, cannot append:
from_public = Ed25519Signer.from_public_hex(public_hex)
Ledger(signer=from_public, storage_path="my-ledger").verify()
```

## Run the tests

```bash
python -m pip install pytest cryptography
python -m pytest -q
```

Expected: `39 passed` (6 adversarial · 10 reasoning-state · 6 monotonic-time · 10 Ed25519 · 7 CLI). CI runs the full suite on Python 3.10, 3.11, 3.12 and 3.13.

## Signing schemes

Two interchangeable signers back the same chain format:

- **HMAC-SHA256** (default, standard library only): writer and verifier share a secret key. `Ledger(key=...)` keeps working exactly as before, even without the `cryptography` package installed.
- **Ed25519** (optional, requires `cryptography`): the writer holds the private key and anyone holding the 32-byte public key can verify the whole chain — but cannot append. A verify-only signer raises `TypeError` on `append()`.

## Auditor CLI

Keys are provided via environment variables, never command-line arguments:

| Variable | Role |
|---|---|
| `SOVEREIGN_RECORD_KEY_HEX` | HMAC secret key (write + verify) |
| `SOVEREIGN_RECORD_PRIVATE_KEY_HEX` | Ed25519 private key (write) |
| `SOVEREIGN_RECORD_PUBLIC_KEY_HEX` | Ed25519 public key (verify only) |

Commands: `keygen`, `init`, `append`, `verify`, `export-anchor` (see `--help`). `--json` gives machine-readable output. The directory must contain `records.jsonl` and `anchor.json` for a nonempty ledger. Success exits **0**; verification failures print to stderr and exit **1**; missing/invalid key or bad usage exits **2**. Do not commit keys or expose them in process arguments.

## External anchoring

After writing records, take a checkpoint and retain it in an independently controlled, durable store:

```bash
python sovereign_record.py export-anchor /path/to/ledger > /independent/store/checkpoint.json
python sovereign_record.py verify /path/to/ledger --external-anchor /independent/store/checkpoint.json
```

**Publish/retain this checkpoint before an attacker can roll back the ledger.** Merely placing the file beside the ledger, or letting the same attacker replace it, provides no rollback protection. The checkpoint must match the ledger's exact count and chain head; later legitimate appends require a newer checkpoint (this API does not verify historical prefixes). An attacker who restores both local files to a previous state passes local verification but fails against the independently retained newer checkpoint.

## What it detects / does not

**Detects:** tamper · truncation · reordering · insertion · backdated monotonic time · coordinated rollback **with a trusted external checkpoint** · invalid reasoning states.

**Does not:** key compromise · coordinated rollback **without** a trusted external checkpoint · signer dishonesty at signing time. The ledger proves what was signed. It does not prove that the signer was truthful.

## Documentation

- [Quickstart](docs/quickstart.md) — full cycle in 5 minutes
- [Architecture](docs/architecture.md) — components and chain design
- [Security model](docs/security.md) — threat model and guarantees
- [API reference](docs/api_reference.md) — complete API and CLI
- [Comparison](docs/comparison.md) — vs transparency logs, Sigstore, WORM storage, blockchains
- [Paper](paper.md) — the failure mode this design answers

## Release sequence

The v1.0.0 gates were external checkpoint export/verification with a passing test suite, green CI on Python 3.10–3.13, and a documented working auditor CLI. Since then the suite has grown (39 tests) and Ed25519 public verification shipped in [v1.1.0](https://github.com/onlyusemore/sovereign-record/releases/tag/v1.1.0). Publish follow-up releases after those gates; then connect Zenodo and obtain the DOI from the published release, and only then add the DOI to `CITATION.cff`. Public review can be requested after release.

## Contributing

Issues and pull requests are welcome. Keep changes in the spirit of the design: fail closed, no repair, keys never in argv. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
