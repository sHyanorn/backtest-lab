"""Vectorized daily backtest with next-open fills (see D013)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

LEVERAGE_TOL = 1e-9
# Trading days between the first and the last close of a daily return's price span:
# the return of row t runs from close t-1 to close t. The target from close t-2, which
# earns its overnight leg, counts as a feature of the row (D036).
INFORMATION_SPAN = 1


@dataclass(frozen=True)
class Costs:
    """Costs per unit of traded notional, in basis points (see D014)."""

    fee_bps: float = 1.0
    slippage_bps: float = 5.0

    def __post_init__(self) -> None:
        if self.fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("costs must be non-negative")

    @property
    def rate(self) -> float:
        return (self.fee_bps + self.slippage_bps) / 1e4


@dataclass(frozen=True)
class Prices:
    """Total-return adjusted open and close panels: dates x tickers."""

    open: pd.DataFrame
    close: pd.DataFrame

    def __post_init__(self) -> None:
        if not (
            self.open.index.equals(self.close.index)
            and self.open.columns.equals(self.close.columns)
        ):
            raise ValueError("open and close must share index and columns")
        if not self.close.index.is_monotonic_increasing or self.close.index.has_duplicates:
            raise ValueError("dates must be strictly increasing")

    @classmethod
    def from_raw(cls, open_: pd.DataFrame, close: pd.DataFrame, adj_close: pd.DataFrame) -> Prices:
        """Apply the close's adjustment factor to the open of the same day."""
        return cls(open=open_ * (adj_close / close), close=adj_close)


@dataclass(frozen=True)
class Result:
    """Daily series from the second price date on.

    Returns before `start` are warm-up zeros: slice from `start` before computing metrics.
    """

    returns: pd.Series  # net daily returns
    gross_returns: pd.Series
    turnover: pd.Series  # sum of |weight change| traded at each open
    costs: pd.Series  # fraction of the open's value paid in fees and slippage
    weights: pd.DataFrame  # positions held from each day's open
    start: pd.Timestamp | None  # first date whose return follows a valid signal


def _check_weights(weights: pd.DataFrame, prices: Prices) -> None:
    unknown = weights.columns.difference(prices.close.columns)
    if len(unknown):
        raise ValueError(f"no prices for {list(unknown)}")
    if not weights.index.equals(prices.close.index):
        raise ValueError("weights must have one row per price date")


def run(
    weights: pd.DataFrame,
    prices: Prices,
    costs: Costs = Costs(),  # noqa: B008 (immutable)
    *,
    max_leverage: float = 1.0,
) -> Result:
    """Backtest target weights decided at each close and filled at the next open.

    The return of day t is (1 + overnight)(1 - cost)(1 + intraday) - 1: the
    positions held from the previous open earn the gap from the previous close
    to today's open, costs are paid on the notional traded to reach the previous
    close's target, and the new positions earn the move to today's close.
    Uninvested capital earns zero. A row with any NaN (warm-up) is flat, and
    tickers without a column have zero weight.
    """
    _check_weights(weights, prices)
    valid = weights.notna().all(axis=1).to_numpy()
    tickers = prices.close.columns
    w_all = weights.reindex(columns=tickers).fillna(0.0).to_numpy(dtype=np.float64, copy=True)
    w_all[~valid] = 0.0
    if (np.abs(w_all).sum(axis=1) > max_leverage + LEVERAGE_TOL).any():
        raise ValueError(f"gross exposure above {max_leverage}")

    # Only tickers that are ever held affect the result.
    active = np.flatnonzero((w_all != 0).any(axis=0))
    w = w_all[:, active]
    o = prices.open.to_numpy(dtype=np.float64)[:, active]
    c = prices.close.to_numpy(dtype=np.float64)[:, active]
    n, k = c.shape
    # held[t]: weights traded at the open of day t (the target from close t-1)
    held = np.zeros((n, k))
    held[1:] = w[:-1]
    prev = np.zeros((n, k))
    prev[1:] = held[:-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        r_on = np.zeros((n, k))
        r_on[1:] = o[1:] / c[:-1] - 1
        r_id = c / o - 1
    _require_prices(r_on, prev != 0, prices, active, "overnight")
    _require_prices(r_id, held != 0, prices, active, "intraday")
    r_on = np.where(prev != 0, r_on, 0.0)
    r_id = np.where(held != 0, r_id, 0.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        f_id = 1 + (held * r_id).sum(axis=1)
        # Weights at the previous close, after drifting with the previous day's intraday move.
        drifted = np.zeros((n, k))
        drifted[1:] = prev[1:] * (1 + r_id[:-1]) / f_id[:-1, None]
        f_on = 1 + (drifted * r_on).sum(axis=1)
        at_open = drifted * (1 + r_on) / f_on[:, None]
    turnover = np.where(f_on > 0, np.abs(held - at_open).sum(axis=1), 0.0)
    cost = costs.rate * turnover

    # A day whose wealth reaches zero or below ends the backtest: -1, then flat.
    ruin = (f_on <= 0) | (1 - cost <= 0) | (f_id <= 0)
    ruin[0] = False
    with np.errstate(invalid="ignore"):
        net = f_on * (1 - cost) * f_id - 1
        gross = f_on * f_id - 1
    if ruin.any():
        day = int(np.argmax(ruin))
        net[day], gross[day] = -1.0, max(min(gross[day], 0.0), -1.0)
        net[day + 1 :] = gross[day + 1 :] = 0.0
        turnover[day + 1 :] = cost[day + 1 :] = 0.0
        held[day + 1 :] = 0.0

    held_all = np.zeros((n, len(tickers)))
    held_all[:, active] = held
    index = prices.close.index
    valid_from = np.flatnonzero(valid[:-1])
    start = pd.Timestamp(index[valid_from[0] + 1]) if len(valid_from) else None
    return Result(
        returns=pd.Series(net[1:], index=index[1:], name="returns"),
        gross_returns=pd.Series(gross[1:], index=index[1:], name="gross_returns"),
        turnover=pd.Series(turnover[1:], index=index[1:], name="turnover"),
        costs=pd.Series(cost[1:], index=index[1:], name="costs"),
        weights=pd.DataFrame(held_all[1:], index=index[1:], columns=tickers),
        start=start,
    )


def _require_prices(
    r: np.ndarray, needed: np.ndarray, prices: Prices, active: np.ndarray, leg: str
) -> None:
    bad = needed & ~np.isfinite(r)
    if bad.any():
        t, j = np.argwhere(bad)[0]
        raise ValueError(
            f"position in {prices.close.columns[active[j]]} on "
            f"{prices.close.index[t]:%Y-%m-%d} without {leg} prices"
        )
