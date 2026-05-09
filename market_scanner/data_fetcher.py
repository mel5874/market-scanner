"""Market data fetching utilities using free data sources."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from .logging_utils import get_logger


REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class MarketDataFetcher:
    """Fetch historical OHLCV data from Yahoo Finance via yfinance."""

    period: str = "6mo"
    interval: str = "1d"

    def fetch_symbol(self, symbol: str) -> pd.DataFrame:
        """Return OHLCV history for one symbol.

        Raises:
            ValueError: if no data is returned or required columns are missing.
        """

        data = yf.download(
            symbol,
            period=self.period,
            interval=self.interval,
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
        )
        if data.empty:
            raise ValueError(f"No market data returned for {symbol}")

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
        if missing:
            raise ValueError(f"Missing columns for {symbol}: {', '.join(missing)}")

        clean = data[REQUIRED_COLUMNS].copy()
        clean.index = pd.to_datetime(clean.index)
        clean = clean.dropna()
        clean["Symbol"] = symbol.upper()
        return clean

    def fetch_watchlist(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        """Fetch data for a list of symbols, skipping failures."""

        results: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                results[symbol.upper()] = self.fetch_symbol(symbol)
            except Exception as exc:  # noqa: BLE001 - keep scanner running per-symbol
                get_logger().warning("Failed to fetch %s: %s", symbol, exc)
        return results
