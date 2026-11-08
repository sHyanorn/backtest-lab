"""Vectorized daily backtest with next-open fills (see D013)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

LEVERAGE_TOL = 1e-9


@dataclass(frozen=True)
class Costs:
    """Costs per unit of traded notional, in basis points (see D014)."""

    fee_bps: float = 1.0
    slippage_bps: float = 5.0

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
    returns: pd.Series  # net daily returns
    gross_returns: pd.Series
    turnover: pd.Series  # sum of |weight change| traded at each open
    costs: pd.Series  # fraction of the open's value paid in fees and slippage
    weights: pd.DataFrame  # positions held from each day's open
    start: pd.Timestamp | None  # first date whose return follows a valid signal

    @property
    def equity(self) -> pd.Series:
        return (1 + self.returns).cumprod()

    @property
    def drawdown(self) -> pd.Series:
        equity = self.equity
        return equity / equity.cummax().clip(lower=1.0) - 1  # W0 = 1 is a peak


def _targets(weights: pd.DataFrame, prices: Prices) -> pd.DataFrame:
    unknown = weights.columns.difference(prices.close.columns)
    if len(unknown):
        raise ValueError(f"no prices for {list(unknown)}")
    extra = weights.index.difference(prices.close.index)
    if len(extra):
        raise ValueError(f"weights on dates without prices, first {extra[0]}")
    return weights.reindex(index=prices.close.index)


def run(
    weights: pd.DataFrame,
    prices: Prices,
    costs: Costs = Costs(),  # noqa: B008 (immutable)
    *,
    max_leverage: float = 1.0,
) -> Result:
    """Backtest target weights decided at each close and filled at the next open.

    The return of day t is (1 + overnight)(1 + intraday) - 1: the positions held
    from the previous open earn the gap from the previous close to today's open,
    then the portfolio is rebalanced to the previous close's target and earns
    the move to today's close. Costs are paid on the traded notional at the
    open, between the two legs. Uninvested capital earns zero. Rows with any NaN
    (warm-up) and tickers without a column count as zero weight.
    """
    targets = _targets(weights, prices)
    valid = targets.notna().all(axis=1).to_numpy()
    w = targets.reindex(columns=prices.close.columns).fillna(0.0).to_numpy(dtype=np.float64)
    if (np.abs(w).sum(axis=1) > max_leverage + LEVERAGE_TOL).any():
        raise ValueError(f"gross exposure above {max_leverage}")

    o = prices.open.to_numpy(dtype=np.float64)
    c = prices.close.to_numpy(dtype=np.float64)
    n, k = c.shape
    # held[t]: weights traded at the open of day t (the target from close t-1)
    held = np.zeros((n, k))
    held[1:] = w[:-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        r_on = np.zeros((n, k))
        r_on[1:] = o[1:] / c[:-1] - 1
        r_id = c / o - 1
    prev = np.zeros((n, k))
    prev[1:] = held[:-1]
    _require_prices(r_on, prev != 0, prices, "overnight")
    _require_prices(r_id, held != 0, prices, "intraday")
    r_on = np.where(prev != 0, r_on, 0.0)
    r_id = np.where(held != 0, r_id, 0.0)

    g_id = (held * r_id).sum(axis=1)
    # Weights at the previous close, after drifting with the previous day's intraday move.
    drifted = np.zeros((n, k))
    with np.errstate(invalid="ignore", divide="ignore"):
        drifted[1:] = prev[1:] * (1 + r_id[:-1]) / (1 + g_id[:-1, None])
    g_on = (drifted * r_on).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        at_open = drifted * (1 + r_on) / (1 + g_on[:, None])
    turnover = np.abs(held - np.nan_to_num(at_open)).sum(axis=1)
    cost = costs.rate * turnover

    gross = _stop_at_ruin((1 + g_on) * (1 + g_id) - 1)
    net = _stop_at_ruin((1 + g_on) * (1 - cost) * (1 + g_id) - 1)

    index = prices.close.index
    valid_from = np.flatnonzero(valid[:-1])
    start = pd.Timestamp(index[valid_from[0] + 1]) if len(valid_from) else None
    return Result(
        returns=pd.Series(net[1:], index=index[1:], name="returns"),
        gross_returns=pd.Series(gross[1:], index=index[1:], name="gross_returns"),
        turnover=pd.Series(turnover[1:], index=index[1:], name="turnover"),
        costs=pd.Series(cost[1:], index=index[1:], name="costs"),
        weights=pd.DataFrame(held[1:], index=index[1:], columns=prices.close.columns),
        start=start,
    )


def _require_prices(r: np.ndarray, needed: np.ndarray, prices: Prices, leg: str) -> None:
    bad = needed & ~np.isfinite(r)
    if bad.any():
        t, j = np.argwhere(bad)[0]
        raise ValueError(
            f"position in {prices.close.columns[j]} on {prices.close.index[t]:%Y-%m-%d} "
            f"without {leg} prices"
        )


def _stop_at_ruin(returns: np.ndarray) -> np.ndarray:
    """A loss of 100% or more ends the backtest: -1 that day, flat afterwards."""
    ruined = np.flatnonzero(returns <= -1)
    if len(ruined):
        out = returns.copy()
        out[ruined[0]] = -1.0
        out[ruined[0] + 1 :] = 0.0
        return out
    return returns
