"""Command-line entry points for scans and backtests."""

from __future__ import annotations

import argparse

from .backtesting import backtest_symbol, summarize_backtest
from .config import load_settings
from .data_fetcher import MarketDataFetcher
from .safety import assert_paper_trading_only
from .scanner import run_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-trading market scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan", help="Run a market scan")
    scan_parser.add_argument("--no-alerts", action="store_true", help="Do not send configured alerts")
    backtest_parser = subparsers.add_parser("backtest", help="Backtest a symbol")
    backtest_parser.add_argument("symbol", help="Ticker symbol, e.g. AAPL or BTC-USD")
    backtest_parser.add_argument("--holding-period", type=int, default=5)

    args = parser.parse_args()
    settings = load_settings()
    assert_paper_trading_only("backtest" if args.command == "backtest" else settings.trading_mode)

    if args.command == "scan":
        signals = run_scan(settings=settings, send_alerts=not args.no_alerts)
        print(f"Generated {len(signals)} logged signals")
        for signal in signals:
            print(f"- {signal.symbol}: score={signal.score} {signal.trade_idea}")
    elif args.command == "backtest":
        fetcher = MarketDataFetcher(period=settings.data_period, interval=settings.data_interval)
        data = fetcher.fetch_symbol(args.symbol)
        results = backtest_symbol(args.symbol, data, settings, holding_period=args.holding_period)
        print(results.tail(20).to_string(index=False) if not results.empty else "No historical signals found")
        print(summarize_backtest(results))


if __name__ == "__main__":
    main()
