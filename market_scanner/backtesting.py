"""Minimal historical backtester for signal ideas."""

from __future__ import annotations

import pandas as pd

from .config import Settings
from .scoring import score_signal
from .signals import detect_signal


def backtest_symbol(symbol: str, data: pd.DataFrame, settings: Settings, holding_period: int = 5) -> pd.DataFrame:
    """Walk forward through history and estimate forward returns after signals."""

    rows: list[dict[str, object]] = []
    min_rows = max(settings.recent_high_window, settings.volume_window, settings.volatility_window) + 2
    for end in range(min_rows, len(data) - holding_period):
        window = data.iloc[:end].copy()
        signal = detect_signal(symbol, window, settings)
        if not signal:
            continue
        signal = score_signal(signal)
        if signal.score < settings.min_score_to_alert:
            continue
        entry = float(data.iloc[end - 1]["Close"])
        exit_price = float(data.iloc[end + holding_period - 1]["Close"])
        rows.append(
            {
                "symbol": symbol.upper(),
                "timestamp": signal.timestamp,
                "score": signal.score,
                "entry": round(entry, 4),
                "exit": round(exit_price, 4),
                "forward_return": round((exit_price / entry) - 1, 6),
                "holding_period": holding_period,
                "reasons": "; ".join(signal.reasons),
            }
        )
    return pd.DataFrame(rows)


def summarize_backtest(results: pd.DataFrame) -> dict[str, float | int]:
    """Return high-level backtest metrics."""

    if results.empty:
        return {"trades": 0, "win_rate": 0.0, "avg_return": 0.0, "total_return": 0.0}
    wins = (results["forward_return"] > 0).mean()
    return {
        "trades": int(len(results)),
        "win_rate": round(float(wins), 4),
        "avg_return": round(float(results["forward_return"].mean()), 6),
        "total_return": round(float(results["forward_return"].sum()), 6),
    }
