"""Application configuration helpers.

Configuration intentionally avoids secrets in code. API tokens and webhook URLs are
read from environment variables only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "BTC-USD", "ETH-USD"]


@dataclass(frozen=True)
class AlertConfig:
    """Optional alert channel configuration loaded from environment variables."""

    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_enabled: bool = False
    discord_webhook_url: str = ""


@dataclass(frozen=True)
class Settings:
    """Runtime settings for scans, paper trading, and storage."""

    watchlist: list[str] = field(default_factory=lambda: DEFAULT_WATCHLIST.copy())
    data_period: str = "6mo"
    data_interval: str = "1d"
    recent_high_window: int = 20
    volume_window: int = 20
    volatility_window: int = 20
    pullback_threshold: float = -0.04
    breakout_buffer: float = 0.002
    unusual_volume_multiple: float = 1.75
    volatility_spike_multiple: float = 1.75
    min_score_to_alert: int = 55
    paper_starting_cash: float = 25_000.0
    max_position_pct: float = 0.10
    max_trade_risk_pct: float = 0.01
    max_trade_risk_dollars: float = 250.0
    max_daily_paper_risk_pct: float = 0.03
    max_open_paper_positions: int = 5
    trading_mode: str = "paper"
    log_path: Path = Path("logs/market_scanner.log")
    database_path: Path = Path("data/market_scanner.sqlite")
    csv_log_path: Path = Path("logs/signals.csv")
    alerts: AlertConfig = field(default_factory=AlertConfig)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    return float(value)


def load_settings() -> Settings:
    """Load settings from environment variables and safe defaults."""

    watchlist_raw = os.getenv("WATCHLIST", ",".join(DEFAULT_WATCHLIST))
    watchlist = [symbol.strip().upper() for symbol in watchlist_raw.split(",") if symbol.strip()]

    alerts = AlertConfig(
        email_enabled=_env_bool("EMAIL_ALERTS_ENABLED"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", ""),
        email_to=os.getenv("EMAIL_TO", ""),
        telegram_enabled=_env_bool("TELEGRAM_ALERTS_ENABLED"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        discord_enabled=_env_bool("DISCORD_ALERTS_ENABLED"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
    )

    return Settings(
        watchlist=watchlist,
        data_period=os.getenv("DATA_PERIOD", "6mo"),
        data_interval=os.getenv("DATA_INTERVAL", "1d"),
        recent_high_window=_env_int("RECENT_HIGH_WINDOW", 20),
        volume_window=_env_int("VOLUME_WINDOW", 20),
        volatility_window=_env_int("VOLATILITY_WINDOW", 20),
        pullback_threshold=_env_float("PULLBACK_THRESHOLD", -0.04),
        breakout_buffer=_env_float("BREAKOUT_BUFFER", 0.002),
        unusual_volume_multiple=_env_float("UNUSUAL_VOLUME_MULTIPLE", 1.75),
        volatility_spike_multiple=_env_float("VOLATILITY_SPIKE_MULTIPLE", 1.75),
        min_score_to_alert=_env_int("MIN_SCORE_TO_ALERT", 55),
        paper_starting_cash=_env_float("PAPER_STARTING_CASH", 25_000.0),
        max_position_pct=_env_float("MAX_POSITION_PCT", 0.10),
        max_trade_risk_pct=_env_float("MAX_TRADE_RISK_PCT", 0.01),
        max_trade_risk_dollars=_env_float("MAX_TRADE_RISK_DOLLARS", 250.0),
        max_daily_paper_risk_pct=_env_float("MAX_DAILY_PAPER_RISK_PCT", 0.03),
        max_open_paper_positions=_env_int("MAX_OPEN_PAPER_POSITIONS", 5),
        trading_mode=os.getenv("TRADING_MODE", "paper"),
        log_path=Path(os.getenv("LOG_PATH", "logs/market_scanner.log")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/market_scanner.sqlite")),
        csv_log_path=Path(os.getenv("CSV_LOG_PATH", "logs/signals.csv")),
        alerts=alerts,
    )
