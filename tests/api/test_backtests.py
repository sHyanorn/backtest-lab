from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backtest_lab.api.main import create_app
from backtest_lab.data.store import connect, load_prices
from backtest_lab.engine.backtest import run
from backtest_lab.engine.metrics import sharpe
from backtest_lab.strategies import MarketData, MovingAverageCrossover
from tests.api.conftest import local_client


def test_lists_every_strategy_with_typed_parameters(client: TestClient) -> None:
    body = client.get("/api/strategies").json()
    by_name = {s["name"]: s for s in body}
    assert set(by_name) == {
        "ma_crossover",
        "mean_reversion",
        "momentum",
        "random_signal",
        "rate_rotation",
    }
    ma = {p["name"]: p for p in by_name["ma_crossover"]["params"]}
    assert ma["fast"] == {
        "name": "fast",
        "type": "int",
        "default": 50,
        "symbol": None,
        "categorical": False,
    }
    assert ma["ticker"]["symbol"] == "ticker"
    rotation = {p["name"]: p["symbol"] for p in by_name["rate_rotation"]["params"]}
    assert rotation["risk_off"] == "ticker" and rotation["long_rate"] == "series"
    assert ma["allow_short"]["type"] == "bool"
    assert by_name["ma_crossover"]["description"].startswith("Long when")
    random = {p["name"]: p["categorical"] for p in by_name["random_signal"]["params"]}
    assert random == {"ticker": False, "seed": True, "hold": False}  # D019


def test_backtest_matches_the_engine(client: TestClient, data_dir: Path) -> None:
    params = {"ticker": "SPY", "fast": 10, "slow": 50}
    r = client.post("/api/backtests", json={"strategy": "ma_crossover", "params": params})
    assert r.status_code == 200, r.text
    body = r.json()

    prices = load_prices(connect(data_dir / "raw"), ["SPY", "IEF"])
    result = run(MovingAverageCrossover(**params).weights(MarketData(prices)), prices)  # type: ignore[arg-type]
    assert result.start is not None
    net = result.returns.loc[result.start :].to_numpy(dtype=np.float64)
    assert body["start"] == f"{result.start:%Y-%m-%d}"
    assert body["n_days"] == len(net)
    assert body["metrics"]["sharpe"] == pytest.approx(sharpe(net), abs=1e-12)
    assert body["costs"] == {"fee_bps": 1.0, "slippage_bps": 5.0}
    assert body["params"] == params | {"allow_short": False}  # defaults are stated
    assert len(body["series"]["dates"]) == len(body["series"]["equity"])


def test_backtest_date_range_and_costs(client: TestClient) -> None:
    base = {"strategy": "momentum", "params": {"lookback": 20}}
    full = client.post("/api/backtests", json=base).json()
    part = client.post(
        "/api/backtests", json=base | {"start": "2012-01-02", "end": "2013-12-31"}
    ).json()
    free = client.post(
        "/api/backtests", json=base | {"costs": {"fee_bps": 0, "slippage_bps": 0}}
    ).json()
    assert part["start"] > full["start"] and part["end"] <= "2013-12-31"
    assert free["metrics"]["cagr"] > full["metrics"]["cagr"]


@pytest.mark.parametrize(
    "body",
    [
        {"strategy": "nope"},
        {"strategy": "ma_crossover", "params": {"fast": "10"}},
        {"strategy": "ma_crossover", "params": {"fast": 10.0}},
        {"strategy": "ma_crossover", "params": {"allow_short": 1}},
        {"strategy": "ma_crossover", "params": {"window": 10}},
        {"strategy": "ma_crossover", "params": {"fast": 60, "slow": 50}},
        {"strategy": "ma_crossover", "params": {"ticker": "QQQ"}},
        {"strategy": "ma_crossover", "extra": 1},
        {"strategy": "ma_crossover", "costs": {"fee_bps": -1}},
        {"strategy": "ma_crossover", "start": "2030-01-01"},
        {"strategy": "rate_rotation", "params": {"long_rate": "DGS30"}},
        # a string parameter must name the right kind of symbol
        {"strategy": "ma_crossover", "params": {"ticker": "DGS10"}},
        {"strategy": "rate_rotation", "params": {"long_rate": "SPY"}},
        {"strategy": "rate_rotation", "params": {"risk_off": "DGS3MO"}},
        # numbers outside +/-1e6
        {"strategy": "mean_reversion", "params": {"entry_z": 10**400}},
        {"strategy": "ma_crossover", "params": {"slow": 10**30}},
        {"strategy": "rate_rotation", "params": {"smoothing": 2**63}},
        {"strategy": "mean_reversion", "params": {"entry_z": -1e7}},
    ],
)
def test_invalid_requests_are_422(client: TestClient, body: dict[str, object]) -> None:
    r = client.post("/api/backtests", json=body)
    assert r.status_code == 422, r.text


def test_rotation_between_one_ticker_is_422(client: TestClient) -> None:
    body = {"strategy": "rate_rotation", "params": {"risk_off": "SPY"}}
    r = client.post("/api/backtests", json=body)
    assert r.status_code == 422
    assert "risk_on and risk_off must differ" in r.text


def test_float_parameter_accepts_an_integer(client: TestClient) -> None:
    r = client.post("/api/backtests", json={"strategy": "mean_reversion", "params": {"entry_z": 2}})
    assert r.status_code == 200
    assert r.json()["params"]["entry_z"] == 2.0


def test_missing_cache_is_503(tmp_path: Path) -> None:
    with local_client(create_app(tmp_path)) as c:
        assert c.post("/api/backtests", json={"strategy": "momentum"}).status_code == 503
        assert c.get("/api/strategies").status_code == 200
