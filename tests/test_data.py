"""The Deribit boundary: a recorded API response in, a snapshot table out (no live network)."""

import json
import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from conftest import RECORDED_RESPONSE as RECORDED
from conftest import REAL_SNAPSHOT
from ivsurface.data import fetch_snapshot, list_snapshots, load_snapshot, save_snapshot
from ivsurface.snapshot import COLUMNS


class RecordedDeribit:
    """Stands in for the HTTP layer: serves the recorded response and remembers what was asked."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        return RECORDED.read_bytes()


@pytest.fixture
def fetched() -> tuple[pd.DataFrame, RecordedDeribit]:
    http = RecordedDeribit()
    return fetch_snapshot("BTC", http_get=http), http


def row(snapshot: pd.DataFrame, strike: float, option_type: str, expiry_day: int) -> dict[str, Any]:
    rows = snapshot.query("strike == @strike and option_type == @option_type")
    rows = rows[[e.day == expiry_day for e in rows["expiry"]]]
    assert len(rows) == 1
    return rows.iloc[0].to_dict()


def test_it_asks_deribit_for_every_option_on_the_underlying(fetched):
    _, http = fetched
    assert len(http.urls) == 1
    assert http.urls[0].startswith("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?")
    assert "currency=BTC" in http.urls[0] and "kind=option" in http.urls[0]


def test_every_instrument_becomes_a_row_in_the_snapshot_schema(fetched):
    snapshot, _ = fetched
    assert list(snapshot.columns) == COLUMNS
    assert len(snapshot) == len(json.loads(RECORDED.read_text())["result"])
    assert set(snapshot["underlying"]) == {"BTC"}


def test_instrument_names_are_parsed_into_strike_type_and_an_0800_utc_expiry(fetched):
    snapshot, _ = fetched
    put = row(snapshot, 54_000.0, "put", 20)  # BTC-20NOV26-54000-P
    assert put["expiry"] == pd.Timestamp(datetime(2026, 11, 20, 8, 0, tzinfo=UTC))
    call = row(snapshot, 100_000.0, "call", 25)  # BTC-25JUN27-100000-C
    assert call["expiry"] == pd.Timestamp(datetime(2027, 6, 25, 8, 0, tzinfo=UTC))


def test_premiums_stay_in_btc_and_mark_iv_becomes_a_decimal(fetched):
    snapshot, _ = fetched
    call = row(snapshot, 50_000.0, "call", 20)  # BTC-20NOV26-50000-C
    assert (call["bid"], call["ask"], call["mark"]) == (0.201, 0.204, 0.20234189)
    assert call["mark_iv"] == pytest.approx(1.1082)  # Deribit sends 110.82 (percent)
    assert call["underlying_price"] == 62_679.45


def test_the_whole_snapshot_shares_one_time_the_earliest_deribit_timestamp(fetched):
    # Deribit stamps each instrument separately, milliseconds apart. A snapshot is one moment:
    # otherwise quotes on the same expiry get slightly different T and split into many slices.
    snapshot, _ = fetched
    assert set(snapshot["snapshot_time"]) == {pd.Timestamp(datetime(2026, 11, 18, 20, 0, 25, 27_000, tzinfo=UTC))}


def test_a_missing_bid_becomes_nan(fetched):
    snapshot, _ = fetched
    no_bid = row(snapshot, 112_000.0, "call", 27)  # BTC-27NOV26-112000-C, bid_price null
    assert math.isnan(no_bid["bid"])
    assert no_bid["ask"] == 0.0001


def test_snapshots_round_trip_through_parquet_with_a_timestamped_name(fetched, tmp_path):
    snapshot, _ = fetched
    path = save_snapshot(snapshot, tmp_path)
    assert path.name == REAL_SNAPSHOT.name  # underlying and earliest quote time, UTC
    assert list_snapshots(tmp_path) == [path]
    pd.testing.assert_frame_equal(load_snapshot(path), snapshot)
