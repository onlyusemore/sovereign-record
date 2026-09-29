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
