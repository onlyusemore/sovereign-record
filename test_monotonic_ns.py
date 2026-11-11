import pytest

from sovereign_record import Ledger, SequenceError


KEY = b"k" * 32


def test_increasing_monotonic_ns_verifies(tmp_path):
    ticks = iter([10, 20, 30])
    led = Ledger(KEY, storage_path=tmp_path / "a",
                 time_fn=lambda: next(ticks))
    led.append("t", "o")
    led.append("t", "o")
    led.append("t", "o")
    led.verify()


def test_equal_monotonic_ns_is_allowed(tmp_path):
    ticks = iter([10, 10])
    led = Ledger(KEY, storage_path=tmp_path / "a",
                 time_fn=lambda: next(ticks))
    led.append("t", "o")
    led.append("t", "o")
    led.verify()


def test_decreasing_monotonic_ns_fails_verify(tmp_path):
    ticks = iter([30, 20])
    led = Ledger(KEY, storage_path=tmp_path / "a",
                 time_fn=lambda: next(ticks))
    led.append("t", "o")
    led.append("t", "o")
    with pytest.raises(SequenceError, match="monotonic_ns went backwards"):
        led.verify()


def test_decreasing_monotonic_ns_fails_on_reload(tmp_path):
    store = tmp_path / "a"
    ticks = iter([30, 20])
    led = Ledger(KEY, storage_path=store, time_fn=lambda: next(ticks))
    led.append("t", "o")
    led.append("t", "o")
    with pytest.raises(SequenceError, match="monotonic_ns went backwards"):
        Ledger(KEY, storage_path=store)
