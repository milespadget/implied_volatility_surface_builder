"""Deribit option chains in, snapshot files out.

Uses Deribit's public JSON-RPC-over-HTTP API (no key needed). One call to
``public/get_book_summary_by_currency`` returns the best bid/ask, mark price, mark IV and
underlying (forward) price for every listed option on an underlying.
"""

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ivsurface.snapshot import COLUMNS

BOOK_SUMMARY_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
EXPIRY_HOUR_UTC = 8
"""Deribit options expire at 08:00 UTC on their expiry date."""

HttpGet = Callable[[str], bytes]


def _urlopen_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ivsurface/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_snapshot(underlying: str = "BTC", *, http_get: HttpGet = _urlopen_get) -> pd.DataFrame:
    """The full option chain for ``underlying`` ("BTC", "ETH", ...) as a snapshot table."""
    url = f"{BOOK_SUMMARY_URL}?{urllib.parse.urlencode({'currency': underlying, 'kind': 'option'})}"
    items = json.loads(http_get(url))["result"]
    # Deribit timestamps each instrument separately (milliseconds apart). A snapshot is one
    # moment, so every row gets the earliest; otherwise one expiry would split into many T.
    taken = datetime.fromtimestamp(min(item["creation_timestamp"] for item in items) / 1000, UTC)
    return pd.DataFrame([_row(underlying, item, taken) for item in items], columns=COLUMNS)


def _row(underlying: str, item: dict[str, Any], taken: datetime) -> dict[str, Any]:
    # Instrument names look like BTC-20NOV26-54000-P.
    _, expiry_code, strike, put_or_call = item["instrument_name"].split("-")
    expiry = datetime.strptime(expiry_code, "%d%b%y").replace(hour=EXPIRY_HOUR_UTC, tzinfo=UTC)
    return {
        "underlying": underlying,
        "strike": float(strike),
        "expiry": pd.Timestamp(expiry),
        "option_type": "call" if put_or_call == "C" else "put",
        "bid": _price(item["bid_price"]),
        "ask": _price(item["ask_price"]),
        "mark": float(item["mark_price"]),
        "mark_iv": float(item["mark_iv"]) / 100.0,  # Deribit quotes IV in percent
        "underlying_price": float(item["underlying_price"]),
        "snapshot_time": pd.Timestamp(taken),
    }


def _price(value: float | None) -> float:
    """Deribit sends null when one side of the book is empty."""
    return np.nan if value is None else float(value)


def save_snapshot(snapshot: pd.DataFrame, directory: Path) -> Path:
    """Write ``snapshot`` as <underlying>_<earliest quote time, UTC>.parquet in ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    underlying = snapshot["underlying"].iat[0]
    taken = snapshot["snapshot_time"].min().strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{underlying}_{taken}.parquet"
    snapshot.to_parquet(path, index=False)
    return path


def load_snapshot(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def list_snapshots(directory: Path) -> list[Path]:
    """Saved snapshots in ``directory``, oldest first (names sort by time within an underlying)."""
    return sorted(directory.glob("*.parquet")) if directory.is_dir() else []
