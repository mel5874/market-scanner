"""Streamlit dashboard for the paper-trading market scanner."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from market_scanner.backtesting import backtest_symbol, summarize_backtest
from market_scanner.config import load_settings
from market_scanner.data_fetcher import MarketDataFetcher
from market_scanner.safety import assert_paper_trading_only
from market_scanner.scanner import run_scan
from market_scanner.storage import SignalStore


st.set_page_config(page_title="Market Scanner", page_icon="📈", layout="wide")
st.title("📈 Market Scanner & Paper-Trading Assistant")
st.warning("Paper trading and alerts only. This dashboard does not place live orders and is not financial advice.")

settings = load_settings()
safety_report = assert_paper_trading_only(settings.trading_mode)
store = SignalStore(settings.database_path, settings.csv_log_path)

with st.sidebar:
    st.header("Configuration")
    st.write("Watchlist")
    st.code(", ".join(settings.watchlist))
    st.caption("Edit WATCHLIST in your environment to change symbols.")
    st.write(f"Mode: {safety_report.mode}")
    st.write(f"Max position: {settings.max_position_pct:.0%}")
    st.write(f"Max trade risk: min({settings.max_trade_risk_pct:.0%}, ${settings.max_trade_risk_dollars:,.0f})")
    st.write(f"Max daily paper risk: {settings.max_daily_paper_risk_pct:.0%}")
    for warning in safety_report.warnings:
        st.warning(warning)
    send_alerts = st.checkbox("Send configured alerts after scan", value=False)
    min_score = st.slider("Minimum score shown", 0, 100, settings.min_score_to_alert)

if st.button("Run scan now", type="primary"):
    with st.spinner("Fetching market data and ranking opportunities..."):
        signals = run_scan(settings=settings, send_alerts=send_alerts)
    st.success(f"Scan complete. {len(signals)} signal(s) logged.")

recent = store.load_recent(limit=200)
if recent:
    df = pd.DataFrame(recent)
    df = df[df["score"] >= min_score]
    st.subheader("Recent Signals")
    st.dataframe(
        df[["timestamp", "symbol", "score", "confidence", "pct_change", "volume_multiple", "risk_reward", "trade_idea"]],
        use_container_width=True,
    )

    st.subheader("Paper Order Proposals")
    proposal_rows = []
    for row in df.head(10).to_dict(orient="records"):
        # Reuse logged values in display-only proposals without broker execution.
        entry_price = float(row["entry_zone_high"] or row["close"])
        stop_loss = float(row["stop_loss"] or entry_price * 0.96)
        risk_per_share = max(entry_price - stop_loss, 0.01)
        max_risk = min(
            settings.paper_starting_cash * settings.max_trade_risk_pct,
            settings.max_trade_risk_dollars,
            settings.paper_starting_cash * settings.max_daily_paper_risk_pct,
        )
        max_allocation = settings.paper_starting_cash * settings.max_position_pct
        quantity = max(0.0, min(max_risk / risk_per_share, max_allocation / entry_price))
        proposal_rows.append(
            {
                "symbol": row["symbol"],
                "side": "BUY-WATCH",
                "quantity": round(quantity, 6),
                "allocation": round(quantity * entry_price, 2),
                "entry_price": round(entry_price, 4),
                "stop_loss": round(stop_loss, 4),
                "target": row["target"],
                "dollars_at_risk": round(quantity * risk_per_share, 2),
                "max_allowed_risk": round(max_risk, 2),
                "mode": "paper-only",
                "warning": "Simulation only. No real order is placed.",
            }
        )
    st.dataframe(pd.DataFrame(proposal_rows), use_container_width=True)
else:
    st.info("No signals logged yet. Run a scan to populate the dashboard.")

st.subheader("Backtest")
col1, col2 = st.columns([2, 1])
with col1:
    symbol = st.text_input("Symbol", value=settings.watchlist[0] if settings.watchlist else "AAPL")
with col2:
    holding_period = st.number_input("Holding period (bars)", min_value=1, max_value=60, value=5)

if st.button("Run backtest"):
    with st.spinner("Fetching history and walking forward..."):
        fetcher = MarketDataFetcher(period=settings.data_period, interval=settings.data_interval)
        data = fetcher.fetch_symbol(symbol)
        results = backtest_symbol(symbol, data, settings, holding_period=int(holding_period))
        summary = summarize_backtest(results)
    st.json(summary)
    st.dataframe(results.tail(100), use_container_width=True)
