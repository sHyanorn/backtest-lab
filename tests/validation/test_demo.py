from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest_lab.data.storage import write_parquet_atomic
from backtest_lab.validation.demo import END, SEARCHES, SETTINGS, START, load_market
from backtest_lab.validation.report import Settings
from tests.factories import price_frame


def test_searches_match_the_pre_registration() -> None:
    # D021: fixed before any real-data run
    grids = {s.name: s.grid for s in SEARCHES}
    assert [len(g) for g in grids.values()] == [128, 34, 100]
    ma = dict(grids["ma_crossover"].axes)
    assert ma["fast"] == (5, 10, 15, 20, 25, 30, 40, 50)
    assert ma["slow"] == (60, 80, 100, 120, 150, 180, 200, 250)
    assert dict(grids["momentum"].axes)["lookback"] == tuple(range(42, 379, 21))
    assert dict(grids["random_signal"].fixed) == {"ticker": "SPY", "hold": 5}
    assert all(dict(g.fixed)["ticker"] == "SPY" for g in grids.values())
    assert START.strftime("%Y-%m-%d") == "1993-01-29"
    assert END.strftime("%Y-%m-%d") == "2026-10-30"
    assert Settings() == SETTINGS


def _store(root: Path, n: int, start: str) -> pd.DataFrame:
    df = price_frame(n=n, start=start)
    write_parquet_atomic(
        df.reset_index().assign(ticker="SPY"), root / "raw" / "prices" / "SPY.parquet"
    )
    return df


def test_load_market_slices_and_adjusts(tmp_path: Path) -> None:
    df = _store(tmp_path, n=40, start="2024-01-02")
    start, end = df.index[5], df.index[30]
    data = load_market(tmp_path, "SPY", start, end)
    close = data.prices.close["SPY"]
    assert close.index[0] == start and close.index[-1] == end
    np.testing.assert_allclose(close.to_numpy(), df["adj_close"].loc[start:end].to_numpy())
    factor = (df["adj_close"] / df["close"]).loc[start:end]
    np.testing.assert_allclose(
        data.prices.open["SPY"].to_numpy(), (df["open"].loc[start:end] * factor).to_numpy()
    )


def test_load_market_needs_the_whole_sample(tmp_path: Path) -> None:
    df = _store(tmp_path, n=40, start="2024-01-02")
    with pytest.raises(ValueError, match="does not cover"):
        load_market(tmp_path, "SPY", df.index[0] - pd.Timedelta(days=1), df.index[-1])
