# sovereign-record

A minimal reference implementation of a signed, append-only record ledger.

## What it does

- **Inference-time binding**: reasoning is signed at write time, or the record is marked `ABSENT` — a first-class signed state.
- **Chain immutability**: each record's HMAC covers the previous chain head.
- **Monotonic sequencing**: gap-free integers, anchored to detect truncation.

## Run the tests

```bash
pip install pytest
python -m pytest test_adversarial.py -v
```

Expected: `5 passed`.

## What it detects

- Tamper (edit a field after signing)
- Truncate (remove the last record)
- Reorder (swap two records)
- Insert (forge a record in the middle)

## What it does not detect

- Key compromise
- Coordinated rollback (record file + anchor rewritten together)
- Signer dishonesty at signing time

The ledger proves what was signed. It does not prove that the signer was truthful.
