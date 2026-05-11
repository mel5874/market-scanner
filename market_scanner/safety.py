"""Safety guardrails that keep the project paper-trading and alert-only."""

from __future__ import annotations

import os
from dataclasses import dataclass


FORBIDDEN_LIVE_TRADING_FLAGS = {
    "LIVE_TRADING_ENABLED",
    "REAL_TRADING_ENABLED",
    "BROKER_LIVE_TRADING",
    "ENABLE_ORDER_EXECUTION",
}

FORBIDDEN_BROKER_SECRET_HINTS = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "BINANCE_API_KEY",
    "BINANCE_SECRET_KEY",
    "COINBASE_API_KEY",
    "COINBASE_SECRET_KEY",
    "IBKR_API_KEY",
    "TRADIER_ACCESS_TOKEN",
    "BROKER_API_KEY",
    "BROKER_SECRET",
)


@dataclass(frozen=True)
class SafetyReport:
    """Result from runtime safety validation."""

    paper_trading_only: bool
    mode: str
    warnings: list[str]


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on", "live", "real"})


def assert_paper_trading_only(mode: str = "paper") -> SafetyReport:
    """Validate that the app is running in paper-trading-only mode.

    The project intentionally has no broker execution adapter. This function adds
    a second runtime guard: attempts to set live/real execution flags raise before
    scans, dashboards, or paper proposals proceed.
    """

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"paper", "paper-only", "alert-only", "backtest"}:
        raise RuntimeError(
            "Unsafe trading mode requested. This project supports only paper, paper-only, alert-only, or backtest modes."
        )

    enabled_live_flags = [name for name in FORBIDDEN_LIVE_TRADING_FLAGS if _truthy(os.getenv(name))]
    if enabled_live_flags:
        joined = ", ".join(sorted(enabled_live_flags))
        raise RuntimeError(f"Live-trading flag(s) detected: {joined}. Disable them before running this app.")

    warnings = [
        f"Broker credential-like environment variable present: {name}"
        for name in FORBIDDEN_BROKER_SECRET_HINTS
        if os.getenv(name)
    ]
    return SafetyReport(paper_trading_only=True, mode=normalized_mode, warnings=warnings)
