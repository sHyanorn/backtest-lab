"""Market data for the API, loaded once from the local cache (D016)."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from backtest_lab.data.store import connect, macro_series, price_panel
from backtest_lab.engine.backtest import Prices
from backtest_lab.strategies import MarketData


@dataclass(frozen=True)
class Market:
    data: MarketData

    @property
    def tickers(self) -> list[str]:
        return list(self.data.prices.close.columns)

    @property
    def series(self) -> list[str]:
        return list(self.data.macro)

    def between(
        self,
        start: date | None,
        end: date | None,
        tickers: list[str],
        also: tuple[str, ...] = (),
    ) -> MarketData:
        """Prices of `tickers` from `start` to `end` inclusive, on the dates at least one of
        them trades, as if only they had been loaded; macro series are kept whole, since
        strategies read them by publication date.

        Tickers in `also`, such as a sweep's benchmark, are added as columns on those dates
        without adding dates of their own (D039)."""
        columns = list(dict.fromkeys([*tickers, *also]))
        close = self.data.prices.close[columns]
        dates = close.index
        keep = close[tickers].notna().any(axis=1).to_numpy(copy=True)
        if start is not None:
            keep &= dates >= pd.Timestamp(start)
        if end is not None:
            keep &= dates <= pd.Timestamp(end)
        if keep.sum() < 2:
            raise ValueError("the date range holds fewer than two trading days")
        return MarketData(
            prices=Prices(open=self.data.prices.open[columns][keep], close=close[keep]),
            macro=self.data.macro,
        )


def load_market(raw_dir: Path) -> Market | None:
    """Every ticker and macro series in the cache, or None when there is no price data."""
    con = connect(raw_dir)
    tables = {row[0] for row in con.execute("SELECT view_name FROM duckdb_views()").fetchall()}
    if "prices" not in tables:
        return None
    tickers = sorted(r[0] for r in con.execute("SELECT DISTINCT ticker FROM prices").fetchall())
    raw = {f: price_panel(con, tickers, f) for f in ("open", "close", "adj_close")}
    prices = Prices.from_raw(raw["open"], raw["close"], raw["adj_close"])
    macro: dict[str, pd.DataFrame] = {}
    if "macro" in tables:
        for (series_id,) in con.execute("SELECT DISTINCT series FROM macro ORDER BY 1").fetchall():
            macro[series_id] = macro_series(con, series_id)
    return Market(MarketData(prices=prices, macro=macro))
