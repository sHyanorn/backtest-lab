"""The registered tests against buy and hold on new samples (D043, METHODS.md Section 8).

(ii) the US market from 1926 to 1993 from the Fama/French daily factors, (iii) the other
eight ETFs, and (i) SPY over the registered sample, post hoc. Each family is cached in
`--cache` as soon as it is done, under a digest of the code, the settings and the data, so
a rerun of the same code on the same data skips it.

Usage: python -m backtest_lab.validation.relative --out DIR --posthoc-out DIR
       [--data-dir data] [--cache data/cache/relative] [--processes N]
"""

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from backtest_lab.data import french
from backtest_lab.data.prices import read_cached
from backtest_lab.data.store import connect, load_prices, price_file, raw_dir
from backtest_lab.engine.backtest import Costs, Prices, run
from backtest_lab.engine.metrics import ANNUALIZATION
from backtest_lab.strategies import STRATEGIES, MarketData
from backtest_lab.validation.demo import END, SEARCHES, load_sample
from backtest_lab.validation.report import buy_and_hold, finite
from backtest_lab.validation.search import Grid, Params, run_grid
from backtest_lab.validation.snooping import Comparison, Criterion, compare, holm

type Matrix = npt.NDArray[np.float64]

REGISTRATION = "D043"
GRIDS = {s.name: s for s in SEARCHES if s.name in ("ma_crossover", "momentum")}
SELECTED: dict[str, Params] = {  # D021's picks on SPY
    "ma_crossover": {"fast": 10, "slow": 200, "allow_short": False},
    "momentum": {"lookback": 273, "allow_short": False},
}
MEAN_BLOCKS = (10.0, 5.0, 20.0, 50.0)  # the first decides
REPS = 10_000
SEED = 0
ALPHA = 0.05

MARKET = "MKT"
FRENCH_END = pd.Timestamp("1993-01-29")  # SPY's first bar in D021, the first day left out
FRENCH_ROWS_SHA256 = "a7e075c925bf89d9e13273307390848530e237a63bacf67086d4a54770adcb85"
FRENCH_COSTS_BPS = (84.0, 0.0, 6.0, 25.0, 50.0)  # the first decides (Jones, 2002)
SPLIT = pd.Timestamp("1960-01-04")
ETFS = ("QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "SHY", "GLD")
# SHA-256 of the rows each ETF sample uses (prices_sha256), fixed in D043
ETF_ROWS_SHA256 = {
    "QQQ": "e33961c8b29f960a3860cf4ea381f2b09645a17de0224208233d5c8f7ba6f9f2",
    "IWM": "9a4b5cb6549e7cfe339a06a3a7274c7dfbe02e9070f6c2378623e2dfa29331f2",
    "EFA": "3e841f8a8b20410d6dc79c725584848f852878bc61932b4c5d48f6691d8e9f9f",
    "EEM": "610e52b1bb5ab439e26fd6be63c05b74451f7d5b894f8b8de188af233aa56710",
    "TLT": "f76bebe14fd0a1e762a4404733ed260bff9585ed66aa809cfdec09ed0d3897b3",
    "IEF": "32c1d0c98c0ac8c6e35e1883edd39942e4e70feac1d16f1ebcdd2085cee89dee",
    "SHY": "41f7c3e229c2bfe0725ec7a6cc83b641f74033ace60aefc276f804813472f2d7",
    "GLD": "aaebb8c231763326eccf90b9e47535060bd467a36d4172b986c2259ebf77b9a7",
}


@dataclass(frozen=True)
class Variant:
    """One way of running a sample's families."""

    name: str
    costs: Costs
    decides: bool = False
    cash: bool = False  # uninvested capital earns RF; Sharpe ratios on excess returns
    after: pd.Timestamp | None = None  # aligned days from this date
    before: pd.Timestamp | None = None  # aligned days before this date

    @property
    def mean_blocks(self) -> tuple[float, ...]:
        return MEAN_BLOCKS if self.decides else MEAN_BLOCKS[:1]


def _bps(one_way: float) -> Costs:
    return Costs(fee_bps=0.0, slippage_bps=one_way)


FRENCH_VARIANTS = (
    Variant("decision", _bps(FRENCH_COSTS_BPS[0]), decides=True),
    *(Variant(f"costs_{c:g}bps", _bps(c)) for c in FRENCH_COSTS_BPS[1:]),
    Variant("cash_earns_rf", _bps(FRENCH_COSTS_BPS[0]), cash=True),
    Variant("before_1960", _bps(FRENCH_COSTS_BPS[0]), before=SPLIT),
    Variant("from_1960", _bps(FRENCH_COSTS_BPS[0]), after=SPLIT),
)
YAHOO_VARIANTS = (Variant("decision", Costs(), decides=True),)


@dataclass(frozen=True)
class Sample:
    name: str
    instrument: str
    data: MarketData
    variants: tuple[Variant, ...]
    stepm_alpha: float  # 0.05 / m, m the deciding families of the question (D043)
    rf: pd.Series | None = None  # daily risk-free return, for the cash variant


def cash_returns(
    returns: pd.Series, weights: pd.Series, costs: pd.Series, rf: pd.Series
) -> pd.Series:
    """Net returns with uninvested capital earning `rf`, from an engine `Result`.

    `weights` are the positions traded at each open: the return of day t is earned by
    the position traded the day before, and the cash beside it earns that day's rate
    before the costs paid at the end of the day.
    """
    idle = 1 - weights.shift(1, fill_value=0.0).abs()
    return returns + idle * rf.loc[returns.index] * (1 - costs)


def matrices(
    sample: Sample, strategy: str, grid: Grid, variant: Variant, processes: int | None
) -> tuple[Matrix, Matrix, pd.DatetimeIndex, list[Params]]:
    """The trial returns and the benchmark on the variant's aligned days."""
    trials = run_grid(strategy, grid, sample.data, variant.costs, processes=processes)
    dates = pd.DatetimeIndex(trials.returns.index)
    x = trials.returns
    b = buy_and_hold(sample.instrument, sample.data, variant.costs).loc[dates]
    if variant.cash:
        assert sample.rf is not None
        rf = sample.rf.loc[dates]
        cols = {}
        for k, params in enumerate(trials.params):
            r = run(
                STRATEGIES[strategy](**params).weights(sample.data),
                sample.data.prices,
                variant.costs,
            )
            with_cash = cash_returns(r.returns, r.weights[sample.instrument], r.costs, sample.rf)
            cols[k] = with_cash.loc[dates]
        x = pd.DataFrame(cols).sub(rf, axis=0)
        b = b - rf  # buy and hold is never in cash on these days
    keep = np.ones(len(dates), dtype=bool)
    if variant.after is not None:
        keep &= dates >= variant.after
    if variant.before is not None:
        keep &= dates < variant.before
    xs: Matrix = x.to_numpy(dtype=np.float64)[keep]
    bs: Matrix = b.to_numpy(dtype=np.float64)[keep]
    return xs, bs, dates[keep], trials.params


def _criterion(c: Comparison, params: list[Params]) -> dict[str, Any]:
    best = int(np.argmax(c.statistic))
    scale = np.sqrt(ANNUALIZATION) if c.criterion is Criterion.SHARPE else ANNUALIZATION
    return {
        "best": {
            "trial": best,
            "params": params[best],
            "annualized": finite(scale * c.statistic[best]),
        },
        "reality_check": c.reality_check,
        "spa": {
            "statistic": c.spa_statistic,
            "lower": c.spa.lower,
            "consistent": c.spa.consistent,
            "upper": c.spa.upper,
        },
        "stepm": [{"trial": k, "params": params[k]} for k in c.stepm],
        "not_studentized": sorted(set(range(len(params))) - set(c.studentized)),
    }


def family(
    sample: Sample,
    strategy: str,
    variant: Variant,
    mean_block: float,
    x: Matrix,
    b: Matrix,
    dates: pd.DatetimeIndex,
    params: list[Params],
) -> dict[str, Any]:
    """Both criteria over the grid, and the setting D021 selected on its own."""
    record: dict[str, Any] = {
        "instrument": sample.instrument,
        "strategy": strategy,
        "variant": variant.name,
        "costs_bps": variant.costs.fee_bps + variant.costs.slippage_bps,
        "cash": "rf" if variant.cash else "zero",
        "mean_block": mean_block,
        "stepm_alpha": sample.stepm_alpha,
        "first": f"{dates[0]:%Y-%m-%d}",
        "last": f"{dates[-1]:%Y-%m-%d}",
        "days": len(dates),
        "settings": x.shape[1],
    }
    grid = compare(x, b, mean_block=mean_block, reps=REPS, seed=SEED, alpha=sample.stepm_alpha)
    record.update({c.value: _criterion(r, params) for c, r in grid.items()})
    if variant.decides and mean_block == MEAN_BLOCKS[0]:
        k = params.index({**params[0], **SELECTED[strategy]})
        one = compare(x[:, [k]], b, mean_block=mean_block, reps=REPS, seed=SEED)
        record["selected"] = {
            "trial": k,
            "params": params[k],
            **{c.value: {"spa_consistent": r.spa.consistent} for c, r in one.items()},
        }
    return record


def _cache_key(sample: Sample, code: str) -> str:
    """A digest of what a sample's families are computed from."""
    data = (sample.data.prices.open, sample.data.prices.close, sample.rf)
    inputs = [code, REPS, SEED, sample.stepm_alpha, *(d.to_csv() for d in data if d is not None)]
    return hashlib.sha256(json.dumps(inputs).encode()).hexdigest()[:16]


def run_sample(
    sample: Sample, cache: Path, code: str, processes: int | None = None
) -> list[dict[str, Any]]:
    """Every family of a sample, read from `cache` when the same `code`, settings and data
    computed it there."""
    folder = cache / _cache_key(sample, code)
    records = []
    for strategy, search in GRIDS.items():
        grid = Grid(axes=search.grid.axes, fixed=(("ticker", sample.instrument),))
        for variant in sample.variants:
            paths = {
                m: folder
                / f"{sample.name}-{sample.instrument}-{strategy}-{variant.name}-L{m:g}.json"
                for m in variant.mean_blocks
            }
            if not all(p.exists() for p in paths.values()):
                x, b, dates, params = matrices(sample, strategy, grid, variant, processes)
                for m, path in paths.items():
                    if not path.exists():
                        rec = family(sample, strategy, variant, m, x, b, dates, params)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            records += [json.loads(p.read_text(encoding="utf-8")) for p in paths.values()]
    return records


def decision(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Holm over the deciding families: SPA consistent p-values at the first block length."""
    families = [
        (r, c.value)
        for r in records
        if r["variant"] == "decision" and r["mean_block"] == MEAN_BLOCKS[0]
        for c in Criterion
    ]
    p = [r[c]["spa"]["consistent"] for r, c in families]
    return [
        {
            "instrument": r["instrument"],
            "strategy": r["strategy"],
            "criterion": c,
            "p": pv,
            "holm": adj,
            "finding": adj <= ALPHA,
        }
        for (r, c), pv, adj in zip(families, p, holm(p), strict=True)
    ]


def french_sample(data_dir: Path) -> tuple[Sample, dict[str, Any]]:
    path = french.zip_file(raw_dir(data_dir))
    content = path.read_bytes()
    if french.rows_sha256(content, FRENCH_END) != FRENCH_ROWS_SHA256:
        raise ValueError("the Fama/French rows before 1993-01-29 differ from those registered")
    frame = french.parse(content)
    used = frame[frame.index < FRENCH_END]
    prices = Prices.from_returns(used[["market"]].rename(columns={"market": MARKET}))
    data = MarketData(prices=prices)
    sample = Sample("french", MARKET, data, FRENCH_VARIANTS, ALPHA / 4, used["rf"])
    meta = {
        "zip_sha256": hashlib.sha256(content).hexdigest(),
        "rows_sha256": FRENCH_ROWS_SHA256,
        "first": f"{used.index[0]:%Y-%m-%d}",
        "last": f"{used.index[-1]:%Y-%m-%d}",
        "rows": len(used),
        "saturday_rows": int((pd.DatetimeIndex(used.index).dayofweek == 5).sum()),
    }
    return sample, meta


def prices_sha256(data_dir: Path, ticker: str) -> str:
    """SHA-256 of the dates, opens, closes and adjusted closes a sample uses, as cached."""
    frame = read_cached(price_file(raw_dir(data_dir), ticker))
    if frame is None:
        raise FileNotFoundError(f"no cached prices for {ticker}")
    used = frame.loc[frame.index <= END, ["open", "close", "adj_close"]]
    text = "".join(
        f"{d:%Y-%m-%d},{float(o)!r},{float(c)!r},{float(a)!r}\n" for d, o, c, a in used.itertuples()
    )
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def yahoo_sample(data_dir: Path, ticker: str, name: str, stepm_alpha: float) -> Sample:
    """`ticker` from its first bar to D021's last day, with D013's fills and D014's costs."""
    if ticker in ETF_ROWS_SHA256 and prices_sha256(data_dir, ticker) != ETF_ROWS_SHA256[ticker]:
        raise ValueError(f"the cached {ticker} prices differ from those registered")
    close = load_prices(connect(raw_dir(data_dir)), [ticker]).close[ticker]
    data = load_sample(data_dir, ticker, close.dropna().index[0], END)
    return Sample(name, ticker, data, YAHOO_VARIANTS, stepm_alpha)


def bridge(data_dir: Path) -> dict[str, Any]:
    """Data check: SPY's daily total return against the Fama/French market where both exist."""
    frame = french.parse(french.zip_file(raw_dir(data_dir)).read_bytes())
    spy = load_prices(connect(raw_dir(data_dir)), ["SPY"]).close["SPY"].pct_change()
    both = pd.concat([spy, frame["market"]], axis=1, join="inner").dropna()
    both = both[both.index >= FRENCH_END]
    diff = both.iloc[:, 0] - both.iloc[:, 1]
    return {
        "first": f"{both.index[0]:%Y-%m-%d}",
        "last": f"{both.index[-1]:%Y-%m-%d}",
        "days": len(both),
        "correlation": float(both.iloc[:, 0].corr(both.iloc[:, 1])),
        "annual_mean_difference": float(ANNUALIZATION * diff.mean()),
    }


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _code() -> dict[str, Any]:
    """The commit the results come from, and whether tracked files differ from it."""
    return {
        "commit": _git("rev-parse", "HEAD").strip(),
        "uncommitted_changes": bool(_git("status", "--porcelain", "--untracked-files=no").strip()),
    }


def _write(path: Path, result: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--posthoc-out", type=Path, required=True, help="for (i), as D029 asks")
    parser.add_argument("--cache", type=Path, default=Path("data/cache/relative"))
    parser.add_argument("--processes", type=int, default=None)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    code = _code()
    head = {"registered": REGISTRATION, **code, "reps": REPS, "seed": SEED, "alpha": ALPHA}
    # Cached families serve only the same commit with the same changes to tracked files.
    version = code["commit"] + _git("diff", "HEAD")

    sample, meta = french_sample(args.data_dir)
    records = run_sample(sample, args.cache, version, args.processes)
    _write(
        args.out / "french.json",
        {
            **head,
            "sample": "(ii) US market, Fama/French daily factors",
            "data": {**meta, "check_against_spy": bridge(args.data_dir)},
            "decision": decision(records),
            "families": records,
        },
    )
    records = [
        r
        for t in ETFS
        for r in run_sample(
            yahoo_sample(args.data_dir, t, "etf", ALPHA / (4 * len(ETFS))),
            args.cache,
            version,
            args.processes,
        )
    ]
    _write(
        args.out / "etfs.json",
        {**head, "sample": "(iii) eight ETFs", "decision": decision(records), "families": records},
    )
    spy = yahoo_sample(args.data_dir, "SPY", "spy", ALPHA / 4)
    records = run_sample(spy, args.cache, version, args.processes)
    args.posthoc_out.mkdir(parents=True, exist_ok=True)
    _write(
        args.posthoc_out / "relative_spy.json",
        {
            **head,
            "post_hoc": True,
            "sample": "(i) SPY over the registered sample, known before D043",
            "families": records,
        },
    )


if __name__ == "__main__":
    main()
