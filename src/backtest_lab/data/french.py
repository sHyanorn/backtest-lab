"""Daily Fama/French 3 factors from the Kenneth R. French Data Library (D043).

The zip is downloaded over HTTPS into the raw directory and is not committed (D003).
Only the market's total return, `Mkt-RF + RF`, and `RF` are used.

Usage: python -m backtest_lab.data.french [--data-dir data]
"""

import argparse
import hashlib
import io
import os
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_lab.data.fetch import with_retries
from backtest_lab.data.store import raw_dir

URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_daily_CSV.zip"
)
HEADER = ["", "Mkt-RF", "SMB", "HML", "RF"]
MISSING = (-99.99, -999.0)  # the library's markers for missing values


def zip_file(raw: Path) -> Path:
    return raw / "french" / "F-F_Research_Data_Factors_daily_CSV.zip"


def _rows(content: bytes) -> list[str]:
    """The data lines of the zip's only file: those after the header, up to a blank line."""
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        names = z.namelist()
        if len(names) != 1:
            raise ValueError(f"expected one file in the zip, got {names}")
        lines = z.read(names[0]).decode("ascii").splitlines()
    heads = [i for i, line in enumerate(lines) if line.replace(" ", "").split(",") == HEADER]
    if len(heads) != 1:
        raise ValueError(f"expected one header {','.join(HEADER)}")
    rows = []
    for line in lines[heads[0] + 1 :]:
        if not line.strip():
            break
        rows.append(line.strip())
    return rows


def _dates(rows: list[str]) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        pd.to_datetime([row.split(",")[0].strip() for row in rows], format="%Y%m%d")
    ).as_unit("us")


def parse(content: bytes) -> pd.DataFrame:
    """Daily `market` (Mkt-RF + RF) and `rf` as decimal returns, indexed by date."""
    rows = _rows(content)
    fields = [row.split(",") for row in rows]
    if not rows or any(len(f) != len(HEADER) for f in fields):
        raise ValueError(f"every row needs {len(HEADER)} fields")
    dates = _dates(rows)
    values = pd.DataFrame([[float(v) for v in f[1:]] for f in fields], columns=HEADER[1:])
    if not dates.is_monotonic_increasing or dates.has_duplicates:
        raise ValueError("dates must be strictly increasing")
    if not np.isfinite(values.to_numpy()).all() or values.isin(MISSING).any(axis=None):
        raise ValueError("missing values")
    return pd.DataFrame(
        {
            "market": ((values["Mkt-RF"] + values["RF"]) / 100).to_numpy(),
            "rf": (values["RF"] / 100).to_numpy(),
        },
        index=dates,
    )


def rows_sha256(content: bytes, before: pd.Timestamp) -> str:
    """SHA-256 of the data lines dated before `before`, as published.

    It identifies the rows a sample uses and stays the same when later months are added.
    """
    rows = _rows(content)
    used = [row for row, day in zip(rows, _dates(rows), strict=True) if day < before]
    return hashlib.sha256("\n".join(used).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class Download:
    path: Path
    sha256: str
    last_modified: str


def _fetch() -> tuple[bytes, str]:
    with urllib.request.urlopen(URL, timeout=60) as resp:
        return resp.read(), str(resp.headers.get("Last-Modified", ""))


def download(raw: Path, fetch: Callable[[], tuple[bytes, str]] = _fetch) -> Download:
    """Fetch the zip and write it into the raw directory once it parses."""
    content, last_modified = with_retries(fetch, "Fama/French")
    parse(content)  # an error page fails here, before anything is written
    path = zip_file(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)
    return Download(path, hashlib.sha256(content).hexdigest(), last_modified)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    d = download(raw_dir(args.data_dir))
    print(f"{d.path}\nsha256 {d.sha256}\nlast-modified {d.last_modified}")


if __name__ == "__main__":
    main()
