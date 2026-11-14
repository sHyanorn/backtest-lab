"""The Fama/French parser on synthetic files laid out like the library's daily file."""

import hashlib
import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from backtest_lab.data.french import download, parse, rows_sha256, zip_file

# Made-up values in percent, in the library's layout.
ROWS = [
    "19260701,    1.00,   -0.25,    0.30,    0.010",
    "19260702,   -2.50,    0.10,   -0.20,    0.020",
    "19260703,    0.40,    0.00,    0.05,    0.010",
]


def _zip(rows: list[str], header: str = ",Mkt-RF,SMB,HML,RF", files: int = 1) -> bytes:
    text = "\n".join(
        [
            "This file was created by using the 202609 CRSP database.",
            "The Tbill return is the simple daily rate.",
            "",
            header,
            *rows,
            "",
            "Copyright 2026 Eugene F. Fama and Kenneth R. French",
        ]
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(files):
            z.writestr(f"F-F_Research_Data_Factors_daily{i or ''}.csv", text + "\n")
    return buf.getvalue()


def test_market_is_the_excess_return_plus_the_risk_free_rate() -> None:
    frame = parse(_zip(ROWS))
    assert list(frame.index) == list(pd.to_datetime(["1926-07-01", "1926-07-02", "1926-07-03"]))
    assert list(frame["market"]) == pytest.approx([0.0101, -0.0248, 0.0041], abs=1e-15)
    assert list(frame["rf"]) == pytest.approx([0.0001, 0.0002, 0.0001], abs=1e-15)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (_zip(ROWS, header=",Mkt-RF,SMB,RF"), "header"),
        (_zip(ROWS, files=2), "one file"),
        (_zip([ROWS[1], ROWS[0]]), "increasing"),
        (_zip([ROWS[0], ROWS[0]]), "increasing"),
        (_zip([*ROWS, "19260705,  -99.99,    0.10,   -0.20,    0.020"]), "missing"),
        (_zip([*ROWS, "19260706,    0.10,    0.10,   -0.20"]), "fields"),
        (_zip([]), "fields"),
    ],
)
def test_rejects_files_it_cannot_read(content: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse(content)


def test_rows_digest_covers_the_used_rows_only() -> None:
    before = pd.Timestamp("1926-07-03")
    digest = rows_sha256(_zip(ROWS), before)
    assert digest == hashlib.sha256("\n".join(r.strip() for r in ROWS[:2]).encode()).hexdigest()
    # A later month appended or a later row revised leaves it unchanged; a used row does not.
    later = [*ROWS[:2], ROWS[2].replace("0.40", "0.41"), "19260706,  0.1,  0.1,  0.1,  0.010"]
    assert rows_sha256(_zip(later), before) == digest
    revised = [ROWS[0].replace("1.00", "1.01"), *ROWS[1:]]
    assert rows_sha256(_zip(revised), before) != digest


def test_download_writes_the_zip_only_once_it_parses(tmp_path: Path) -> None:
    content = _zip(ROWS)
    got = download(tmp_path, fetch=lambda: (content, "Tue, 27 Oct 2026 15:18:47 GMT"))
    assert got.path == zip_file(tmp_path)
    assert got.path.read_bytes() == content
    assert got.sha256 == hashlib.sha256(content).hexdigest()
    assert got.last_modified == "Tue, 27 Oct 2026 15:18:47 GMT"
    with pytest.raises(zipfile.BadZipFile):
        download(tmp_path, fetch=lambda: (b"<html>error</html>", ""))
    assert got.path.read_bytes() == content
