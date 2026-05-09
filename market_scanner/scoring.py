"""Opportunity scoring and plain-English trade idea generation."""

from __future__ import annotations

from .signals import Signal


def score_signal(signal: Signal) -> Signal:
    """Assign a simple 0-100 score and confidence value to a signal."""

    score = 0
    if signal.is_breakout:
        score += 25
    if signal.is_unusual_volume:
        score += min(25, int(10 + signal.volume_multiple * 6))
    if signal.is_big_mover:
        score += min(20, int(abs(signal.pct_change) * 350))
    if signal.is_volatility_spike:
        score += min(15, int(signal.volatility_multiple * 5))
    if signal.is_pullback:
        score += 10

    if signal.is_breakout and signal.is_unusual_volume:
        score += 10
    if signal.is_pullback and signal.is_unusual_volume:
        score += 5

    signal.score = max(0, min(100, score))
    signal.confidence = round(signal.score / 100, 2)
    return add_trade_idea(signal)


def add_trade_idea(signal: Signal) -> Signal:
    """Add an educational paper-trade idea with entry, stop, target, and R/R."""

    close = signal.close
    if signal.is_pullback and not signal.is_breakout:
        entry_low = close * 0.985
        entry_high = close * 1.005
        stop_loss = min(signal.recent_low, close * 0.96)
        target = close + (close - stop_loss) * 1.8
        setup = "pullback/reversal watch"
    else:
        entry_low = close * 0.995
        entry_high = close * 1.015
        stop_loss = max(signal.recent_high * 0.985, close * 0.965) if signal.is_breakout else close * 0.96
        target = close + (close - stop_loss) * 2.0
        setup = "momentum/breakout watch"

    risk = max(entry_high - stop_loss, 0.01)
    reward = max(target - entry_high, 0.0)
    risk_reward = reward / risk if risk else 0.0

    signal.entry_zone_low = round(entry_low, 4)
    signal.entry_zone_high = round(entry_high, 4)
    signal.stop_loss = round(stop_loss, 4)
    signal.target = round(target, 4)
    signal.risk_reward = round(risk_reward, 2)

    why = "; ".join(signal.reasons)
    signal.trade_idea = (
        f"{signal.symbol} is a {setup}. Why it may be moving: {why}. "
        f"Paper entry zone: {signal.entry_zone_low:.2f}-{signal.entry_zone_high:.2f}. "
        f"Invalidate below {signal.stop_loss:.2f}; first target near {signal.target:.2f}. "
        f"Estimated risk/reward: {signal.risk_reward:.2f}:1. Confidence: {signal.confidence:.0%}. "
        "Educational paper-trade idea only, not financial advice."
    )
    return signal


def rank_signals(signals: list[Signal]) -> list[Signal]:
    """Score and rank signals from strongest to weakest."""

    scored = [score_signal(signal) for signal in signals]
    return sorted(scored, key=lambda item: (item.score, abs(item.pct_change)), reverse=True)
