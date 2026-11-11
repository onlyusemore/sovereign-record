import json

import pytest

import sovereign_record as sr


def test_keygen_hmac_prints_64_hex_chars(capsys):
    assert sr.main(["keygen", "--scheme", "hmac"]) == 0
    out = capsys.readouterr().out.strip()
    assert len(out) == 64
    bytes.fromhex(out)


def test_keygen_ed25519_prints_keypair(capsys):
    assert sr.main(["keygen", "--scheme", "ed25519"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["scheme"] == "ed25519"
    assert len(data["private_key_hex"]) == 64
    assert len(data["public_key_hex"]) == 64
    # The printed pair round-trips through the signer.
    signer = sr.Ed25519Signer.from_private_hex(data["private_key_hex"])
    assert signer.public_key_hex() == data["public_key_hex"]


def test_init_creates_empty_verifiable_ledger(tmp_path, capsys):
    d = tmp_path / "led"
    assert sr.main(["init", str(d)]) == 0
    assert (d / "records.jsonl").exists()
    # An empty ledger still needs a key to verify, but must load and verify.
    import os
    os.environ["SOVEREIGN_RECORD_KEY_HEX"] = "ab" * 32
    assert sr.main(["verify", str(d)]) == 0
    assert "verified" in capsys.readouterr().out


def test_append_and_verify_full_cycle_ed25519(tmp_path, monkeypatch, capsys):
    d = tmp_path / "led"
    assert sr.main(["init", str(d)]) == 0
    signer = sr.Ed25519Signer.generate()
    monkeypatch.setenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX", signer.private_key_hex())
    capsys.readouterr()
    assert sr.main(["append", str(d), "tok-1", "output-1"]) == 0
    out = capsys.readouterr().out
    assert "appended seq=0" in out
    assert "reasoning_state=ABSENT" in out

    reasoning = tmp_path / "steps.json"
    reasoning.write_text(json.dumps([
        {"source": "ai", "content": "considered the options"},
    ]))
    assert sr.main(["append", str(d), "tok-2", "output-2",
                    "--reasoning", str(reasoning), "--json"]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["status"] == "appended"
    assert rec["seq"] == 1
    assert rec["reasoning_state"] == "PRESENT"

    # Any third party verifies with the public key only.
    monkeypatch.delenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX")
    monkeypatch.setenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", signer.public_key_hex())
    assert sr.main(["verify", str(d), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "verified"
    assert data["count"] == 2


def test_append_with_hmac_writer(tmp_path, monkeypatch, capsys):
    d = tmp_path / "led"
    assert sr.main(["init", str(d)]) == 0
    monkeypatch.setenv("SOVEREIGN_RECORD_KEY_HEX", "cd" * 32)
    monkeypatch.delenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", raising=False)
    monkeypatch.delenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX", raising=False)
    assert sr.main(["append", str(d), "tok", "out"]) == 0
    assert sr.main(["verify", str(d)]) == 0


def test_public_only_signer_cannot_append(tmp_path, monkeypatch, capsys):
    d = tmp_path / "led"
    assert sr.main(["init", str(d)]) == 0
    signer = sr.Ed25519Signer.generate()
    monkeypatch.setenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX", signer.private_key_hex())
    assert sr.main(["append", str(d), "tok", "out"]) == 0
    monkeypatch.delenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX")
    monkeypatch.setenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", signer.public_key_hex())
    with pytest.raises(SystemExit):
        sr.main(["append", str(d), "tok2", "out2"])


def test_verify_json_reports_failure(tmp_path, monkeypatch, capsys):
    d = tmp_path / "led"
    assert sr.main(["init", str(d)]) == 0
    signer = sr.Ed25519Signer.generate()
    monkeypatch.setenv("SOVEREIGN_RECORD_PRIVATE_KEY_HEX", signer.private_key_hex())
    assert sr.main(["append", str(d), "tok", "out"]) == 0
    lines = (d / "records.jsonl").read_text().strip().split("\n")
    obj = json.loads(lines[0])
    obj["output"] = "tampered"
    lines[0] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    (d / "records.jsonl").write_text("\n".join(lines) + "\n")
    monkeypatch.setenv("SOVEREIGN_RECORD_PUBLIC_KEY_HEX", signer.public_key_hex())
    assert sr.main(["verify", str(d), "--json"]) == 1
    err = json.loads(capsys.readouterr().err)
    assert err["status"] == "failed"
    assert "error" in err
