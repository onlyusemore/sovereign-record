import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from sovereign_record import (
    Ledger, Step, VerificationError, SequenceError,
)


def _make_ledger(tmp, key):
    return Ledger(key, storage_path=tmp / "ledger")


def _read_lines(p):
    return p.read_text().splitlines()


def _write_lines(p, lines):
    p.write_text("\n".join(lines) + "\n")


def test_happy_path_and_reload():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        led.append("tok-A", "recommend: 5mg",
                   reasoning=[Step(source="model_emitted", content="weight 70kg")])
        led.append("tok-B", "recommend: 10mg")
        led.verify()
        Ledger(key, storage_path=base / "ledger").verify()
        env = {**os.environ, "SOVEREIGN_RECORD_KEY_HEX": key.hex()}
        script = Path(__file__).with_name("sovereign_record.py")
        cmd = [sys.executable, str(script)]
        result = subprocess.run(cmd + ["verify", str(base / "ledger")],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "verified"
        exported = subprocess.run(cmd + ["export-anchor", str(base / "ledger")],
                                  env=env, capture_output=True, text=True)
        assert exported.returncode == 0, exported.stderr
        anchor = base / "independent-checkpoint.json"
        anchor.write_text(exported.stdout)
        result = subprocess.run(cmd + ["verify", str(base / "ledger"),
                                       "--external-anchor", str(anchor)],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert subprocess.run(cmd + ["verify", str(base / "missing")],
                              env=env, capture_output=True).returncode == 1
        assert subprocess.run(cmd + ["verify", str(base / "ledger")],
                              env={**env, "SOVEREIGN_RECORD_KEY_HEX": os.urandom(32).hex()},
                              capture_output=True).returncode == 1
        assert subprocess.run(cmd + ["verify", str(base / "ledger")],
                              env={**env, "SOVEREIGN_RECORD_KEY_HEX": ""},
                              capture_output=True).returncode == 2
        anchor.write_text("null")  # An explicit anchor must never be ignored.
        assert subprocess.run(cmd + ["verify", str(base / "ledger"),
                                     "--external-anchor", str(anchor)],
                              env=env, capture_output=True).returncode == 1


def test_attack_tamper():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        led.append("tok-A", "recommend: 5mg")
        led.append("tok-B", "recommend: 10mg")
        records = base / "ledger" / "records.jsonl"
        lines = _read_lines(records)
        obj = json.loads(lines[0])
        obj["output"] = "recommend: 50mg"
        lines[0] = json.dumps(obj, separators=(",", ":"), sort_keys=True)
        _write_lines(records, lines)
        with pytest.raises(VerificationError):
            Ledger(key, storage_path=base / "ledger")


def test_attack_truncate():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        for i in range(3):
            led.append(f"tok-{i}", f"out-{i}")
        records = base / "ledger" / "records.jsonl"
        lines = _read_lines(records)
        _write_lines(records, lines[:-1])
        with pytest.raises(SequenceError):
            Ledger(key, storage_path=base / "ledger")


def test_attack_reorder():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        for i in range(3):
            led.append(f"tok-{i}", f"out-{i}")
        records = base / "ledger" / "records.jsonl"
        lines = _read_lines(records)
        lines[0], lines[1] = lines[1], lines[0]
        _write_lines(records, lines)
        with pytest.raises((SequenceError, VerificationError)):
            Ledger(key, storage_path=base / "ledger")


def test_attack_insert():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        for i in range(3):
            led.append(f"tok-{i}", f"out-{i}")
        records = base / "ledger" / "records.jsonl"
        lines = _read_lines(records)
        forged = {
            "seq": 1, "token": "forged", "output": "forged",
            "reasoning_state": "ABSENT", "reasoning": [],
            "monotonic_ns": 0, "wall_time_s": 0.0,
            "prev_chain": "00" * 32, "signature": "00" * 32,
        }
        lines.insert(1, json.dumps(forged, separators=(",", ":"), sort_keys=True))
        _write_lines(records, lines)
        with pytest.raises((SequenceError, VerificationError)):
            Ledger(key, storage_path=base / "ledger")


def test_attack_coordinated_rollback():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        led = _make_ledger(base, key)
        led.append("tok-0", "out-0")
        records = base / "ledger" / "records.jsonl"
        local_anchor = base / "ledger" / "anchor.json"
        old_records = records.read_bytes()
        old_anchor = local_anchor.read_bytes()
        led.append("tok-1", "out-1")
        led.append("tok-2", "out-2")
        external = led.export_anchor()
        assert external["count"] == 3

        # Attacker controls both local files, but not the independently held copy.
        records.write_bytes(old_records)
        local_anchor.write_bytes(old_anchor)
        rolled_back = Ledger(key, storage_path=base / "ledger")
        rolled_back.verify()  # Without external evidence, the attack succeeds.
        with pytest.raises(SequenceError):
            rolled_back.verify(external_anchor=external)
        with pytest.raises(VerificationError):
            rolled_back.verify(external_anchor={"count": 1, "chain": external["chain"]})
        with pytest.raises(VerificationError):
            rolled_back.verify(external_anchor={"count": 1, "chain": "é" * 64})

        independent = base / "checkpoint.json"
        independent.write_text(json.dumps(external))
        script = Path(__file__).with_name("sovereign_record.py")
        result = subprocess.run(
            [sys.executable, str(script), "verify", str(base / "ledger"),
             "--external-anchor", str(independent)],
            env={**os.environ, "SOVEREIGN_RECORD_KEY_HEX": key.hex()},
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "external anchor count" in result.stderr
