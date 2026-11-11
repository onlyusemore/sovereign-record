import pytest

from sovereign_record import Record, Step


def _rec(**kw):
    base = dict(seq=0, token="t", output="o", reasoning_state="ABSENT", reasoning=(),
                monotonic_ns=1, wall_time_s=1.0, prev_chain="00" * 32)
    base.update(kw)
    return Record(**base)


@pytest.mark.parametrize("bad", ["BOGUS", "", "present", "Absent"])
def test_unknown_reasoning_state_is_rejected(bad):
    with pytest.raises(ValueError):
        _rec(reasoning_state=bad)


@pytest.mark.parametrize("bad", [None, 0, 1.5, b"ABSENT", ("ABSENT",)])
def test_non_string_reasoning_state_is_rejected(bad):
    with pytest.raises(TypeError):
        _rec(reasoning_state=bad)


def test_valid_states_and_existing_checks_still_work():
    _rec()
    _rec(reasoning_state="PRESENT", reasoning=(Step(source="ai", content="x"),))
    with pytest.raises(ValueError):
        _rec(reasoning_state="ABSENT", reasoning=(Step(source="ai", content="x"),))
    with pytest.raises(ValueError):
        _rec(reasoning_state="PRESENT", reasoning=())
    with pytest.raises(TypeError):
        _rec(reasoning_state="PRESENT", reasoning=("not a Step",))
