from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
REAL_SNAPSHOT = FIXTURES / "BTC_20261118T200025Z.parquet"
"""A full Deribit BTC option chain, taken 2026-11-18 20:00 UTC."""
RECORDED_RESPONSE = FIXTURES / "deribit_book_summary_btc.json"
"""A trimmed get_book_summary_by_currency response from the same fetch."""
