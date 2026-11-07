from pathlib import Path

import pandas as pd
import pytest

from backtest_lab.data.macro import Frequency, parse
from backtest_lab.data.storage import write_parquet_atomic
from backtest_lab.data.store import connect, macro_series, price_panel
from tests.factories import price_frame


@pytest.fixture
def root(tmp_path: Path) -> Path:
    tmp_path = tmp_path / "it's [data]"  # quote and glob characters in the path
    for i, ticker in enumerate(["SPY", "TLT"]):
        df = price_frame(n=10, seed=i).reset_index()
        df.insert(0, "ticker", ticker)
        write_parquet_atomic(df, tmp_path / "prices" / f"{ticker}.parquet")
    csv = "observation_date,DGS10\n2024-01-02,4.0\n2024-01-03,4.1\n"
    write_parquet_atomic(parse(csv, "DGS10", Frequency.DAILY), tmp_path / "macro" / "DGS10.parquet")
    return tmp_path


def test_price_panel_is_wide_by_ticker(root: Path) -> None:
    panel = price_panel(connect(root), ["TLT", "SPY"], "close")
    assert list(panel.columns) == ["TLT", "SPY"]
    assert len(panel) == 10
    expected = price_frame(n=10, seed=0)["close"]
    assert panel["SPY"].to_numpy() == pytest.approx(expected.to_numpy())


def test_unknown_ticker_and_field_are_rejected(root: Path) -> None:
    con = connect(root)
    with pytest.raises(KeyError):
        price_panel(con, ["SPY", "QQQ"])
    with pytest.raises(ValueError):
        price_panel(con, ["SPY"], "close; DROP VIEW prices")


def test_macro_joins_prices_on_date(root: Path) -> None:
    con = connect(root)
    rows = con.execute(
        "SELECT p.date, m.value FROM prices p JOIN macro m ON p.date = m.date "
        "WHERE p.ticker = 'SPY' ORDER BY p.date"
    ).fetchall()
    assert [r[1] for r in rows] == [4.0, 4.1]
    df = macro_series(con, "DGS10")
    assert df["available_date"].iloc[0] == pd.Timestamp("2024-01-03")
