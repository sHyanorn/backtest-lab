import pandas as pd
import pytest

from backtest_lab.data.macro import Frequency, parse

DAILY_CSV = """observation_date,DGS10
2024-03-28,4.20
2024-03-29,.
2024-04-01,4.33
"""

MONTHLY_CSV = """observation_date,UNRATE
2024-01-01,3.7
2024-02-01,
2024-12-01,4.1
"""


def test_daily_values_are_available_next_business_day() -> None:
    df = parse(DAILY_CSV, "DGS10", Frequency.DAILY)
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2024-03-28", "2024-04-01"]
    assert list(df["available_date"].dt.strftime("%Y-%m-%d")) == ["2024-03-29", "2024-04-02"]
    assert list(df["value"]) == [4.20, 4.33]
    assert (df["series"] == "DGS10").all()


def test_daily_values_skip_fed_holidays() -> None:
    csv = "observation_date,DGS10\n2024-11-08,4.31\n2024-10-11,4.10\n"
    df = parse(csv, "DGS10", Frequency.DAILY)
    # 2024-11-11 (Veterans Day) and 2024-10-14 (Columbus Day): Fed closed, stocks open
    assert list(df["available_date"].dt.strftime("%Y-%m-%d")) == ["2024-11-12", "2024-10-15"]


def test_monthly_values_are_available_at_end_of_next_month() -> None:
    df = parse(MONTHLY_CSV, "UNRATE", Frequency.MONTHLY)
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2024-01-01", "2024-12-01"]
    assert list(df["available_date"].dt.strftime("%Y-%m-%d")) == ["2024-02-29", "2025-01-31"]


def test_late_release_uses_actual_release_date() -> None:
    csv = "observation_date,UNRATE\n2025-08-01,4.3\n2025-09-01,4.4\n"
    df = parse(csv, "UNRATE", Frequency.MONTHLY)
    assert list(df["available_date"].dt.strftime("%Y-%m-%d")) == ["2025-09-30", "2025-11-20"]


def test_dates_match_price_date_type() -> None:
    df = parse(DAILY_CSV, "DGS10", Frequency.DAILY)
    assert df["date"].dtype == pd.DatetimeIndex([], dtype="datetime64[us]").dtype


def test_rejects_unexpected_layout() -> None:
    with pytest.raises(ValueError, match="unexpected columns"):
        parse("<html>error</html>", "DGS10", Frequency.DAILY)


@pytest.mark.network
def test_download_dgs10() -> None:
    from backtest_lab.data.macro import download

    df = download("DGS10")
    assert df["date"].min() == pd.Timestamp("1962-01-02")
