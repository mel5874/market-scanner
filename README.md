# Market Scanner & Paper-Trading Assistant

A Python MVP that scans a configurable stock/crypto watchlist for unusual movement, ranks opportunities, logs every generated signal, sends optional alerts, and provides a simple Streamlit dashboard.

> **Paper trading and alert-only:** this project does **not** contain broker integrations, live trading, or real-money order execution.

## Risk warnings

- This software is for education, research, alerting, and paper trading only.
- It is **not financial, investment, tax, or legal advice**.
- Market data can be delayed, inaccurate, missing, or adjusted after the fact.
- Backtests are hypothetical and can overfit; they do not guarantee future results.
- Paper-trading results often differ from live trading because of slippage, spreads, liquidity, latency, partial fills, and emotions.
- You are responsible for every decision you make. Never risk money you cannot afford to lose.

## Safety guardrails

This codebase is intentionally paper-only:

- There is no broker adapter, no order-routing module, and no live order execution path.
- Paper proposals use the display-only side `BUY-WATCH`; they are not transmitted anywhere.
- Startup fails if a live-trading mode or live-order flag is detected, such as `LIVE_TRADING_ENABLED=true`, `REAL_TRADING_ENABLED=true`, `BROKER_LIVE_TRADING=true`, or `ENABLE_ORDER_EXECUTION=true`.
- Broker credential-like environment variables are surfaced as safety warnings so you do not accidentally mix this tool with real trading credentials.
- Alerts are informational only and always include paper-trading / not-financial-advice language.

## Features

- Scans stocks and crypto symbols supported by Yahoo Finance via `yfinance`.
- Detects:
  - biggest price movers,
  - unusual volume,
  - breakouts above recent highs,
  - sharp pullbacks,
  - volatility spikes.
- Scores and ranks opportunities with a transparent 0-100 scoring model.
- Generates plain-English paper-trade ideas with:
  - why it may be moving,
  - possible entry zone,
  - invalidation/stop-loss level,
  - target and risk/reward estimate,
  - confidence score.
- Applies maximum paper-risk controls for position size, per-trade risk, daily paper risk, and open paper positions.
- Sends optional email, Telegram, or Discord alerts.
- Stores signal logs in SQLite and CSV, plus operational logs in `logs/market_scanner.log`.
- Includes a Streamlit dashboard.
- Includes historical walk-forward backtesting.
- Keeps configuration and secrets out of source code.

## Project structure

```text
market_scanner/
  alerting.py        # email, Telegram, Discord alert delivery
  backtesting.py     # historical strategy testing
  cli.py             # command-line interface
  config.py          # environment-based settings, no hard-coded secrets
  data_fetcher.py    # yfinance data fetching
  logging_utils.py   # console/file logging setup
  paper_trading.py   # paper-only portfolio/order proposals with risk caps
  safety.py          # runtime guardrails against live trading
  scanner.py         # end-to-end scan orchestration
  scoring.py         # opportunity ranking and trade ideas
  signals.py         # signal detection
  storage.py         # SQLite and CSV signal logs
dashboard.py         # Streamlit dashboard
tests/               # pytest coverage for core logic
requirements.txt     # Python dependencies
.env.example         # safe configuration template
```

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and edit values as needed:

   ```bash
   cp .env.example .env
   ```

4. Load environment variables before running commands:

   ```bash
   set -a
   source .env
   set +a
   ```

## Configuration

The app uses safe defaults, but you can override settings with environment variables.

| Variable | Purpose | Example |
| --- | --- | --- |
| `WATCHLIST` | Comma-separated Yahoo Finance symbols | `AAPL,MSFT,NVDA,SPY,BTC-USD` |
| `DATA_PERIOD` | yfinance period | `6mo` |
| `DATA_INTERVAL` | yfinance interval | `1d` |
| `MIN_SCORE_TO_ALERT` | Minimum score saved/alerted | `55` |
| `PAPER_STARTING_CASH` | Paper portfolio starting cash | `25000` |
| `MAX_POSITION_PCT` | Max paper allocation per idea | `0.10` |
| `MAX_TRADE_RISK_PCT` | Max risk per paper idea as a percent of starting cash | `0.01` |
| `MAX_TRADE_RISK_DOLLARS` | Absolute dollar cap on risk per paper idea | `250` |
| `MAX_DAILY_PAPER_RISK_PCT` | Max simulated daily risk budget | `0.03` |
| `MAX_OPEN_PAPER_POSITIONS` | Max simultaneous simulated positions | `5` |
| `TRADING_MODE` | Must be `paper`, `paper-only`, or `alert-only` | `paper` |
| `LOG_PATH` | Operational log file | `logs/market_scanner.log` |
| `DATABASE_PATH` | SQLite signal log | `data/market_scanner.sqlite` |
| `CSV_LOG_PATH` | CSV signal log | `logs/signals.csv` |

Optional alert secrets must be supplied via environment variables only. Do not commit real values.

## Run a scan

```bash
python -m market_scanner.cli scan --no-alerts
```

Remove `--no-alerts` to use configured alert channels. Scans log operational events to `LOG_PATH` and append qualifying signals to SQLite/CSV.

## Run the dashboard

```bash
streamlit run dashboard.py
```

The dashboard can run scans, show recent logged signals, display risk-capped paper-only order proposals, and launch a simple backtest. It cannot place real orders.

## Run a backtest

```bash
python -m market_scanner.cli backtest AAPL --holding-period 5
```

Backtests walk forward through historical bars and estimate the forward return after qualifying signals.

## Alerts

All alert channels are optional and disabled by default.

### Email

Set:

```bash
EMAIL_ALERTS_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_app_password
EMAIL_FROM=alerts@example.com
EMAIL_TO=you@example.com
```

### Telegram

Set:

```bash
TELEGRAM_ALERTS_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Discord

Set:

```bash
DISCORD_ALERTS_ENABLED=true
DISCORD_WEBHOOK_URL=your_webhook_url
```

## Paper-trading workflow only

1. Run a scan or dashboard refresh.
2. Review the logged signal, explanation, confidence, entry zone, invalidation level, and risk/reward estimate.
3. Review the risk-capped paper proposal. Quantity is limited by both max allocation and max risk settings.
4. Record any simulated outcome manually or extend the in-memory paper portfolio for research. Do not connect this app to a broker.

## Testing

```bash
pytest
```

## Important limitations

- Yahoo Finance data is a free source and may be delayed or incomplete.
- The scoring model is intentionally simple for the MVP and should be validated before relying on it.
- There is no broker connectivity by design.
- Signal logs are append-only and may contain duplicates if you run scans repeatedly on the same bar.
