# Quickstart — 5 minutes

A complete cycle: generate keys, create a ledger, write records, and verify from the outside.

## Install

```bash
git clone https://github.com/onlyusemore/sovereign-record
cd sovereign-record
python -m pip install pytest cryptography   # cryptography is optional (Ed25519)
```

## 1. Generate keys

```bash
python sovereign_record.py keygen --scheme ed25519
```

Output (values will differ):

```json
{
  "scheme": "ed25519",
  "private_key_hex": "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
  "public_key_hex": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
}
```

Keep the private key with the writer. Publish the public key — anyone can use it to verify, nobody can use it to write.

## 2. Create a ledger and write a record

```bash
export SOVEREIGN_RECORD_PRIVATE_KEY_HEX="<private_key_hex from step 1>"

python sovereign_record.py init my-ledger
python sovereign_record.py append my-ledger "case-42" "Recommend amoxicillin 500mg"
# appended seq=0 reasoning_state=ABSENT
```

To bind reasoning steps to a record:

```bash
cat > steps.json <<'EOF'
[{"source": "model", "content": "Allergy check passed; first-line antibiotic indicated"}]
EOF
python sovereign_record.py append my-ledger "case-43" "Recommend amoxicillin 500mg" --reasoning steps.json
# appended seq=1 reasoning_state=PRESENT
```

## 3. Verify — as any third party

The auditor needs only the public key:

```bash
export SOVEREIGN_RECORD_PUBLIC_KEY_HEX="<public_key_hex from step 1>"
unset SOVEREIGN_RECORD_PRIVATE_KEY_HEX

python sovereign_record.py verify my-ledger
# verified

python sovereign_record.py verify my-ledger --json
# {"chain": "...", "count": 2, "status": "verified"}
```

A public-key holder cannot write:

```bash
python sovereign_record.py append my-ledger "case-44" "..."
# error: append requires a private key: a public-only signer cannot write
```

## 4. Export a checkpoint (rollback protection)

```bash
python sovereign_record.py export-anchor my-ledger > checkpoint.json
# store checkpoint.json somewhere the writer cannot touch
```

Later audits check the live ledger against the retained checkpoint:

```bash
python sovereign_record.py verify my-ledger --external-anchor checkpoint.json
```

If both local files were rolled back to an earlier consistent state, local verification still passes — but the external checkpoint catches it.

## 5. Run the test suite

```bash
python -m pytest -q
# 39 passed
```

## Python API in 10 lines

```python
from sovereign_record import Ed25519Signer, Ledger

signer = Ed25519Signer.generate()
public_hex = signer.public_key_hex()          # publish this
led = Ledger(signer=signer, storage_path="my-ledger")
led.append("case-1", "output", reasoning=[Step(source="model", content="...")])
led.verify()

# Any third party, public key only:
from_public = Ed25519Signer.from_public_hex(public_hex)
Ledger(signer=from_public, storage_path="my-ledger").verify()
```

Next: [architecture](architecture.md) · [security model](security.md) · [API reference](api_reference.md)
