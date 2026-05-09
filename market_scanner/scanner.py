"""End-to-end orchestration for the market scanner MVP."""

from __future__ import annotations

from .alerting import AlertManager
from .config import Settings, load_settings
from .data_fetcher import MarketDataFetcher
from .logging_utils import configure_logging
from .scoring import rank_signals
from .safety import assert_paper_trading_only
from .signals import Signal, detect_signals
from .storage import SignalStore


def run_scan(settings: Settings | None = None, send_alerts: bool = True) -> list[Signal]:
    """Fetch data, detect/rank opportunities, log them, and optionally alert."""

    settings = settings or load_settings()
    logger = configure_logging(settings.log_path)
    safety_report = assert_paper_trading_only(settings.trading_mode)
    for warning in safety_report.warnings:
        logger.warning("Safety warning: %s", warning)

    logger.info("Starting scan in %s mode for %d symbols", safety_report.mode, len(settings.watchlist))
    fetcher = MarketDataFetcher(period=settings.data_period, interval=settings.data_interval)
    market_data = fetcher.fetch_watchlist(settings.watchlist)
    logger.info("Fetched data for %d/%d symbols", len(market_data), len(settings.watchlist))

    ranked = rank_signals(detect_signals(market_data, settings))
    logged = [signal for signal in ranked if signal.score >= settings.min_score_to_alert]
    logger.info("Detected %d signals; %d met minimum score %d", len(ranked), len(logged), settings.min_score_to_alert)

    store = SignalStore(settings.database_path, settings.csv_log_path)
    try:
        store.save_signals(logged)
        logger.info("Saved %d signal(s) to SQLite and CSV logs", len(logged))
    except Exception:
        logger.exception("Failed to persist signal logs")
        raise

    if send_alerts and logged:
        try:
            results = AlertManager(settings.alerts).send(logged)
            logger.info("Alert results: %s", ", ".join(results))
        except Exception:
            logger.exception("Alert delivery failed; signals remain logged")
    elif send_alerts:
        logger.info("No alert sent because no signal met the configured threshold")
    else:
        logger.info("Alert delivery skipped by caller")
    return logged
