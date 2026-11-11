import pytest

from sovereign_record import (
    Ledger, Record, SequenceError,
    chain_hash, canonical_bytes,
)

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


def test_append_rejects_backwards_monotonic_ns_before_persisting(tmp_path):
    store = tmp_path / "a"
    ticks = iter([30, 20])
    led = Ledger(KEY, storage_path=store, time_fn=lambda: next(ticks))
    led.append("t", "o")
    with pytest.raises(SequenceError, match="refusing to append"):
        led.append("t", "o")
    # The invalid record was never written and the ledger stays usable.
    assert (store / "records.jsonl").read_text().count("\n") == 1
    led.verify()
    reloaded = Ledger(KEY, storage_path=store)
    reloaded.verify()
    assert reloaded._next_seq == 1


def test_append_rejects_backwards_ns_after_reload(tmp_path):
    store = tmp_path / "a"
    led = Ledger(KEY, storage_path=store)
    led.append("t", "o")  # real monotonic_ns, huge value
    reloaded = Ledger(KEY, storage_path=store, time_fn=lambda: 0)
    with pytest.raises(SequenceError, match="refusing to append"):
        reloaded.append("t", "o")


def _ledger_with_forged_backwards_ns(store):
    """Build a ledger whose second record is correctly signed and chained
    but carries an older monotonic_ns, as if the writer bypassed append()."""
    led = Ledger(KEY, storage_path=store)
    led.append("t", "o")
    unsigned = Record(
        seq=1, token="t", output="o", reasoning_state="ABSENT", reasoning=(),
        monotonic_ns=0, wall_time_s=1.0, prev_chain=led._last_chain.hex(),
        signature="",
    )
    signed = led._replace_signature(unsigned, led._sign(unsigned))
    led._records.append(signed)
    led._last_chain = chain_hash(
        led._last_chain, canonical_bytes(signed.payload_for_signing()))
    led._next_seq = 2
    return led


def test_verify_rejects_backwards_ns_with_valid_signature(tmp_path):
    led = _ledger_with_forged_backwards_ns(tmp_path / "a")
    with pytest.raises(SequenceError, match="monotonic_ns went backwards"):
        led.verify()


def test_reload_rejects_backwards_ns_with_valid_signature(tmp_path):
    store = tmp_path / "a"
    led = _ledger_with_forged_backwards_ns(store)
    led._persist(led._records[-1])
    with pytest.raises(SequenceError, match="monotonic_ns went backwards"):
        Ledger(KEY, storage_path=store)
