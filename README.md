# sovereign-record

[![Tests](https://github.com/onlyusemore/sovereign-record/actions/workflows/tests.yml/badge.svg)](https://github.com/onlyusemore/sovereign-record/actions/workflows/tests.yml)

A minimal reference implementation of a signed, append-only record ledger.

## What it does

- **Inference-time binding**: reasoning is signed at write time, or the record is marked `ABSENT` — a first-class signed state.
- **Chain immutability**: each record's HMAC covers the previous chain head.
- **Monotonic sequencing**: gap-free integers, anchored to detect truncation.
- **External checkpoint verification**: a separately retained chain head detects coordinated rollback of both local files.

## Run the tests

```bash
python -m pip install pytest
python -m pytest test_adversarial.py -v
```

Expected: `6 passed`. CI runs these tests on Python 3.10, 3.11, 3.12 and 3.13.

## Auditor CLI

The auditor needs the same secret HMAC key as the signer (at least 32 bytes), provided via the environment rather than a command-line argument. For example, for an **existing** ledger and a securely supplied key:

```bash
export SOVEREIGN_RECORD_KEY_HEX="$(cat /secure/location/key.hex)"
python sovereign_record.py verify /path/to/ledger
```

The directory must already contain `records.jsonl` and `anchor.json` for a nonempty ledger. Success prints `verified` and exits **0**; verification failures (including missing files, wrong key and mismatched external checkpoints) print to stderr and exit **1**; missing/invalid key or bad CLI usage exits **2**. Do not commit the key or expose it in a process argument. A real audit requires trusted distribution of the HMAC key; a compromised key lets an attacker forge records.

## External anchoring

After writing records, take a checkpoint using `Ledger.export_anchor()` (a JSON-compatible `{"count": ..., "chain": ...}` object) or:

```bash
python sovereign_record.py export-anchor /path/to/ledger > /independent/store/checkpoint.json
```

**Publish/retain this checkpoint in an independently controlled, durable store before an attacker can roll back the ledger.** Merely placing the file beside the ledger, or letting the same attacker replace it, provides no rollback protection. This library exports and checks snapshots; it does *not* publish them, prove their timestamp, or implement an external append-only service.

Later, retrieve the *trusted* checkpoint and check it against a freshly loaded ledger:

```bash
python sovereign_record.py verify /path/to/ledger --external-anchor /trusted/checkpoint.json
```

Or in Python, `Ledger(key, storage_path=path).verify(external_anchor=checkpoint)`. The checkpoint must match the ledger's **exact** count and chain head. If more records have legitimately been appended since that checkpoint, export a newer checkpoint before verifying the full ledger against it; this API does not verify historical prefixes. An attacker who restores both local files to a previous state passes local verification but fails against the independently retained newer checkpoint.

## What it detects

- Tamper (edit a field after signing)
- Truncate (remove the last record)
- Reorder (swap two records)
- Insert (forge a record in the middle)
- Coordinated rollback **when checked against a trusted external checkpoint**

## What it does not detect

- Key compromise
- Coordinated rollback **without** a trusted external checkpoint (or if the attacker also controls it)
- Signer dishonesty at signing time

The ledger proves what was signed. It does not prove that the signer was truthful.

## Release sequence

The v1.0.0 gates are external checkpoint export/verification with six passing tests, green CI on Python 3.10–3.13, and a documented working auditor CLI. Publish the GitHub release **after** those gates; then connect Zenodo and obtain the DOI from the published release, and only then add the DOI to `CITATION.cff`. Public review can be requested after release; responses belong to a subsequent version, not the v1.0.0 gates.
