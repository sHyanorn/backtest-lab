"""Performance metrics as defined in METHODS.md Section 1."""

import numpy as np
import numpy.typing as npt
import pandas as pd

ANNUALIZATION = 252
ZERO_TOL = 1e-12  # a standard deviation below this counts as zero (D020)

type Returns = pd.Series | npt.ArrayLike


def _array(returns: Returns) -> npt.NDArray[np.float64]:
    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 1:
        raise ValueError("returns must be one-dimensional")
    if not np.isfinite(r).all():
        raise ValueError("returns must be finite")
    return r


def _ratio(num: float, den: float) -> float:
    return float(num / den) if den >= ZERO_TOL else float("nan")


def cagr(returns: Returns) -> float:
    r = _array(returns)
    if len(r) == 0:
        return float("nan")
    wealth = float(np.prod(1 + r))
    return wealth ** (ANNUALIZATION / len(r)) - 1 if wealth > 0 else float("nan")


def annual_volatility(returns: Returns) -> float:
    r = _array(returns)
    if len(r) < 2:
        return float("nan")
    s = float(np.std(r, ddof=1))
    return 0.0 if s < ZERO_TOL else float(s * np.sqrt(ANNUALIZATION))


def sharpe(returns: Returns, risk_free: float = 0.0) -> float:
    excess = _array(returns) - risk_free
    if len(excess) < 2:
        return float("nan")
    return float(np.sqrt(ANNUALIZATION)) * _ratio(
        float(excess.mean()), float(np.std(excess, ddof=1))
    )


def downside_deviation(returns: Returns, target: float = 0.0) -> float:
    r = _array(returns)
    if len(r) == 0:
        return float("nan")
    shortfall = np.minimum(r - target, 0.0)
    return float(np.sqrt(ANNUALIZATION) * np.sqrt(np.mean(shortfall**2)))


def sortino(returns: Returns, target: float = 0.0) -> float:
    r = _array(returns)
    if len(r) == 0:
        return float("nan")
    return _ratio(ANNUALIZATION * float(np.mean(r - target)), downside_deviation(r, target))


def max_drawdown(returns: Returns) -> float:
    r = _array(returns)
    wealth = np.concatenate([[1.0], np.cumprod(1 + r)])  # W0 = 1 is a peak
    return float(np.min(wealth / np.maximum.accumulate(wealth) - 1))


def calmar(returns: Returns) -> float:
    mdd = max_drawdown(returns)
    return _ratio(cagr(returns), abs(mdd))


def summarize(returns: Returns) -> dict[str, float]:
    return {
        "cagr": cagr(returns),
        "annual_volatility": annual_volatility(returns),
        "sharpe": sharpe(returns),
        "sortino": sortino(returns),
        "max_drawdown": max_drawdown(returns),
        "calmar": calmar(returns),
    }
