from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backtest_lab.api.main import create_app
from backtest_lab.data.macro import Frequency, available_dates
from backtest_lab.data.store import write_parquet_atomic
from tests.factories import price_frame

N_DAYS = 1800  # more than the 1,512 aligned days a report needs plus warm-up


def write_cache(root: Path, n: int = N_DAYS) -> None:
    """Synthetic SPY and IEF prices and two daily rates in the cache layout."""
    for seed, ticker in enumerate(["SPY", "IEF"]):
        df = price_frame(n=n, start="2010-01-04", seed=seed).reset_index()
        df.insert(0, "ticker", ticker)
        write_parquet_atomic(df, root / "raw" / "prices" / f"{ticker}.parquet")
    dates = pd.bdate_range("2010-01-04", periods=n).as_unit("us")
    rng = np.random.default_rng(7)
    for series_id, level in [("DGS10", 3.0), ("DGS3MO", 2.0)]:
        frame = pd.DataFrame(
            {
                "series": series_id,
                "date": dates,
                "value": level + np.cumsum(rng.normal(0, 0.02, n)),
                "available_date": available_dates(dates, Frequency.DAILY),
            }
        )
        write_parquet_atomic(frame, root / "raw" / "macro" / f"{series_id}.parquet")


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("data")
    write_cache(root)
    return root


def local_client(app: FastAPI) -> TestClient:
    """A client that sends the Host header of a local browser."""
    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    with local_client(create_app(data_dir)) as c:
        yield c
