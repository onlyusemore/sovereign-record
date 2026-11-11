import json

import pytest

import sovereign_record as sr
from sovereign_record import (
    Ed25519Signer, HmacSigner, Ledger, SequenceError, VerificationError,
)


@pytest.fixture
def signer():
    return Ed25519Signer.generate()


def _make_ledger(signer, tmp_path, **kw):
    return Ledger(signer=signer, storage_path=tmp_path / "a", **kw)


def test_ed25519_valid_signature_verifies(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    led.append("tok", "out", reasoning=[sr.Step(source="ai", content="why")])
    led.verify()


def test_ed25519_public_key_can_verify_without_private_key(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    public = Ed25519Signer.from_public_hex(signer.public_key_hex())
    reloaded = Ledger(signer=public, storage_path=tmp_path / "a")
    reloaded.verify()
    assert reloaded.export_anchor() == led.export_anchor()


def test_ed25519_verify_only_signer_cannot_append(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    public = Ed25519Signer.from_public_hex(signer.public_key_hex())
    reloaded = Ledger(signer=public, storage_path=tmp_path / "a")
    with pytest.raises(TypeError, match="verify-only"):
        reloaded.append("tok", "out")


def test_ed25519_forged_signature_is_rejected(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    good = led._records[0]
    forged = sr.Record(
        seq=good.seq, token=good.token, output="tampered output",
        reasoning_state=good.reasoning_state, reasoning=good.reasoning,
        monotonic_ns=good.monotonic_ns, wall_time_s=good.wall_time_s,
        prev_chain=good.prev_chain, signature=good.signature,
    )
    led._records[0] = forged
    with pytest.raises(VerificationError, match="signature mismatch"):
        led.verify()


def test_ed25519_wrong_public_key_is_rejected(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    wrong = Ed25519Signer.generate()
    with pytest.raises(VerificationError, match="signature mismatch"):
        Ledger(signer=wrong, storage_path=tmp_path / "a")


def test_ed25519_tampered_disk_record_is_rejected(signer, tmp_path):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    lines = (tmp_path / "a" / "records.jsonl").read_text().strip().split("\n")
    obj = json.loads(lines[0])
    obj["output"] = "tampered"
    lines[0] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    (tmp_path / "a" / "records.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(VerificationError):
        Ledger(signer=signer, storage_path=tmp_path / "a")


def test_hmac_ledger_still_works_unchanged(tmp_path):
    led = Ledger(b"k" * 32, storage_path=tmp_path / "a")
    led.append("tok", "out")
    led.verify()


def test_ledger_rejects_key_and_signer_together(signer, tmp_path):
    with pytest.raises(ValueError, match="not both"):
        Ledger(b"k" * 32, signer=signer, storage_path=tmp_path / "a")


def test_cli_verifies_with_ed25519_public_key(signer, tmp_path, monkeypatch, capsys):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    monkeypatch.setenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", signer.public_key_hex())
    monkeypatch.delenv("SOVEREIGN_RECORD_KEY_HEX", raising=False)
    assert sr.main(["verify", str(tmp_path / "a")]) == 0
    assert "verified" in capsys.readouterr().out


def test_cli_rejects_tampered_ledger_with_ed25519(signer, tmp_path, monkeypatch, capsys):
    led = _make_ledger(signer, tmp_path)
    led.append("tok", "out")
    lines = (tmp_path / "a" / "records.jsonl").read_text().strip().split("\n")
    obj = json.loads(lines[0])
    obj["output"] = "tampered"
    lines[0] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    (tmp_path / "a" / "records.jsonl").write_text("\n".join(lines) + "\n")
    monkeypatch.setenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", signer.public_key_hex())
    monkeypatch.delenv("SOVEREIGN_RECORD_KEY_HEX", raising=False)
    assert sr.main(["verify", str(tmp_path / "a")]) == 1
    assert "verification failed" in capsys.readouterr().err
