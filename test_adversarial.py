import json
import os
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
