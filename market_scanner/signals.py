"""Signal detection for unusual movement and technical setups."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import pandas as pd

from .config import Settings


@dataclass
class Signal:
    """A single ranked market opportunity candidate."""

    symbol: str
    timestamp: str
    close: float
    previous_close: float
    pct_change: float
    volume: float
    avg_volume: float
    volume_multiple: float
    recent_high: float
    recent_low: float
    volatility: float
    avg_volatility: float
    volatility_multiple: float
    is_big_mover: bool
    is_unusual_volume: bool
    is_breakout: bool
    is_pullback: bool
    is_volatility_spike: bool
    reasons: list[str]
    score: int = 0
    confidence: float = 0.0
    trade_idea: str = ""
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_reward: float = 0.0

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record["reasons"] = "; ".join(self.reasons)
        return record


def _latest_timestamp(index: pd.Index) -> str:
    latest = index[-1]
    if isinstance(latest, pd.Timestamp):
        return latest.to_pydatetime().isoformat()
    return datetime.now(timezone.utc).isoformat()


def detect_signal(symbol: str, data: pd.DataFrame, settings: Settings) -> Signal | None:
    """Detect the most recent signal for a symbol using daily OHLCV data."""

    min_rows = max(settings.recent_high_window, settings.volume_window, settings.volatility_window) + 2
    if len(data) < min_rows:
        return None

    frame = data.copy().sort_index()
    frame["PctChange"] = frame["Close"].pct_change()
    frame["TrueRangePct"] = (frame["High"] - frame["Low"]) / frame["Close"].replace(0, pd.NA)

    latest = frame.iloc[-1]
    previous = frame.iloc[-2]
    history = frame.iloc[:-1]

    recent_high = float(history["High"].tail(settings.recent_high_window).max())
    recent_low = float(history["Low"].tail(settings.recent_high_window).min())
    avg_volume = float(history["Volume"].tail(settings.volume_window).mean())
    avg_volatility = float(history["TrueRangePct"].tail(settings.volatility_window).mean())

    close = float(latest["Close"])
    previous_close = float(previous["Close"])
    pct_change = (close / previous_close) - 1 if previous_close else 0.0
    volume = float(latest["Volume"])
    volume_multiple = volume / avg_volume if avg_volume else 0.0
    latest_volatility = latest["TrueRangePct"]
    volatility = 0.0 if pd.isna(latest_volatility) else float(latest_volatility)
    volatility_multiple = volatility / avg_volatility if avg_volatility else 0.0

    is_big_mover = abs(pct_change) >= 0.03
    is_unusual_volume = volume_multiple >= settings.unusual_volume_multiple
    is_breakout = close >= recent_high * (1 + settings.breakout_buffer)
    is_pullback = pct_change <= settings.pullback_threshold
    is_volatility_spike = volatility_multiple >= settings.volatility_spike_multiple

    reasons: list[str] = []
    if is_big_mover:
        direction = "up" if pct_change > 0 else "down"
        reasons.append(f"big price mover {direction} {pct_change:.1%}")
    if is_unusual_volume:
        reasons.append(f"unusual volume at {volume_multiple:.1f}x the {settings.volume_window}-day average")
    if is_breakout:
        reasons.append(f"breakout above the prior {settings.recent_high_window}-day high")
    if is_pullback:
        reasons.append(f"sharp pullback of {pct_change:.1%}")
    if is_volatility_spike:
        reasons.append(f"volatility spike at {volatility_multiple:.1f}x normal range")

    if not reasons:
        return None

    return Signal(
        symbol=symbol.upper(),
        timestamp=_latest_timestamp(frame.index),
        close=round(close, 4),
        previous_close=round(previous_close, 4),
        pct_change=round(pct_change, 6),
        volume=round(volume, 2),
        avg_volume=round(avg_volume, 2),
        volume_multiple=round(volume_multiple, 3),
        recent_high=round(recent_high, 4),
        recent_low=round(recent_low, 4),
        volatility=round(volatility, 6),
        avg_volatility=round(avg_volatility, 6),
        volatility_multiple=round(volatility_multiple, 3),
        is_big_mover=is_big_mover,
        is_unusual_volume=is_unusual_volume,
        is_breakout=is_breakout,
        is_pullback=is_pullback,
        is_volatility_spike=is_volatility_spike,
        reasons=reasons,
    )


def detect_signals(market_data: dict[str, pd.DataFrame], settings: Settings) -> list[Signal]:
    """Detect signals for every symbol and return non-empty candidates."""

    signals: list[Signal] = []
    for symbol, frame in market_data.items():
        signal = detect_signal(symbol, frame, settings)
        if signal:
            signals.append(signal)
    return signals
