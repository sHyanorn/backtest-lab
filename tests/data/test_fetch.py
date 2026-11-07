import pytest

from backtest_lab.data.fetch import FetchError, with_retries


def test_retries_then_succeeds() -> None:
    delays: list[float] = []
    calls = iter([RuntimeError("429"), RuntimeError("429"), None])

    def fn() -> str:
        error = next(calls)
        if error is not None:
            raise error
        return "ok"

    assert with_retries(fn, "SPY", sleep=delays.append) == "ok"
    assert delays == [2.0, 4.0]


def test_gives_up_with_source_and_reason() -> None:
    delays: list[float] = []

    def fn() -> None:
        raise RuntimeError("Too Many Requests")

    with pytest.raises(FetchError) as info:
        with_retries(fn, "SPY", sleep=delays.append)
    assert delays == [2.0, 4.0, 8.0, 16.0]
    assert info.value.source == "SPY"
    assert "Too Many Requests" in info.value.reason
