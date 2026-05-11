import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os

# Mock data for demonstration
def load_mock_data():
    signals = [
        {"symbol": "AAPL", "signal": "BUY", "confidence": 85, "explanation": "This BUY signal was triggered because the stock price has shown a strong upward trend over the last 5 trading days, with an average daily increase of 2.5%. High trading volume (above average by 30%) indicates strong investor interest and conviction. Technical indicators like the Relative Strength Index (RSI) at 65 suggest the stock is not overbought yet, and the Moving Average Convergence Divergence (MACD) shows bullish momentum. These factors combined contribute to the high 85% confidence score.", "timestamp": "2023-05-09 10:00:00"},
        {"symbol": "GOOGL", "signal": "SELL", "confidence": 70, "explanation": "This SELL signal was triggered due to the stock being in an overbought condition, with the RSI reaching 75, which often precedes a price correction. The price has risen sharply in the past week (up 8%), but volume has been declining, suggesting weakening momentum. The MACD indicator is showing signs of divergence, and support levels are being tested. These bearish signals contribute to the 70% confidence score.", "timestamp": "2023-05-09 10:05:00"},
        {"symbol": "TSLA", "signal": "HOLD", "confidence": 60, "explanation": "This HOLD signal indicates the stock is in a consolidation phase with no clear directional bias. The price has been moving sideways for the past 10 days, with low volatility. Volume is average, and technical indicators like RSI (around 50) and MACD are neutral. While there are some positive news mentions, the lack of strong momentum keeps the confidence at 60%.", "timestamp": "2023-05-09 10:10:00"},
    ]
    history = signals + [
        {"symbol": "MSFT", "signal": "BUY", "confidence": 90, "explanation": "This BUY signal was triggered by a breakout above key resistance levels, with the stock closing above its 200-day moving average. Volume spiked 50% above average, confirming the move. RSI at 55 shows room for upside, and earnings reports were positive. These strong fundamentals and technicals contribute to the 90% confidence.", "timestamp": "2023-05-08 15:00:00"},
        {"symbol": "AMZN", "signal": "SELL", "confidence": 75, "explanation": "This SELL signal was triggered as the stock failed to break above resistance, leading to a rejection candle. Volume was high but selling pressure increased. RSI at 70 indicates overbought conditions, and MACD histogram is declining. Recent news about regulatory scrutiny added to the bearish outlook, scoring 75% confidence.", "timestamp": "2023-05-08 15:05:00"},
    ]
    watchlist = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]
    performance = {"total_signals": 10, "win_rate": 75.0, "total_return": 12.5}
    return signals, history, watchlist, performance

# Load data
signals, history, watchlist, performance = load_mock_data()

# App title
st.title("Market Scanner Dashboard")

# Latest scan timestamp
latest_scan = max([s["timestamp"] for s in signals])
st.subheader(f"Latest Scan: {latest_scan}")

# Performance summary cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Signals", performance["total_signals"])
with col2:
    st.metric("Win Rate (%)", f"{performance['win_rate']:.1f}")
with col3:
    st.metric("Total Return (%)", f"{performance['total_return']:.1f}")

# Charts for signals
st.subheader("Signal Distribution")
signal_counts = pd.DataFrame(signals).groupby("signal").size().reset_index(name="count")
fig = px.bar(signal_counts, x="signal", y="count", title="Signals by Type")
st.plotly_chart(fig)

# Confidence scores chart
st.subheader("Confidence Scores")
fig2 = px.scatter(pd.DataFrame(signals), x="symbol", y="confidence", color="signal", size="confidence", title="Signal Confidence")
st.plotly_chart(fig2)

# Current Signals with explanations and color-coded confidence
st.subheader("Current Signals")
def color_confidence(conf):
    if conf >= 80:
        return "🟢 High"
    elif conf >= 60:
        return "🟡 Medium"
    else:
        return "🔴 Low"

signals_df = pd.DataFrame(signals)
signals_df["Confidence Level"] = signals_df["confidence"].apply(color_confidence)
st.dataframe(signals_df[["symbol", "signal", "Confidence Level", "explanation", "timestamp"]])

# Signal history table
st.subheader("Signal History")
history_df = pd.DataFrame(history)
st.dataframe(history_df)

# Watchlist management
st.subheader("Watchlist")
new_symbol = st.text_input("Add Symbol to Watchlist")
if st.button("Add"):
    if new_symbol and new_symbol not in watchlist:
        watchlist.append(new_symbol.upper())
        st.success(f"Added {new_symbol.upper()} to watchlist")

st.write("Current Watchlist:", ", ".join(watchlist))

# Paper Trading
st.subheader("Paper Trading")
trade_symbol = st.selectbox("Select Symbol", watchlist)
trade_action = st.selectbox("Action", ["BUY", "SELL"])
trade_quantity = st.number_input("Quantity", min_value=1, value=10)
if st.button("Execute Trade"):
    st.success(f"Simulated {trade_action} of {trade_quantity} shares of {trade_symbol}")

# Start a scan
st.subheader("Start a New Scan")
if st.button("Scan Markets"):
    st.info("Scanning markets... (Simulated)")
    # In real app, trigger scan logic
    st.success("Scan completed!")

# Data Storage
st.subheader("Data Storage")
st.write("Signals and history are stored locally in JSON files for demonstration. In production, use a database like SQLite or PostgreSQL.")
st.write("Watchlist and trades are stored in session state (temporary).")