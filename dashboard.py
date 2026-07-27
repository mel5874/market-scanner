import streamlit as st
import pandas as pd
import yfinance as yf
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import csv

from market_scanner.scanner import run_scan as real_run_scan
from market_scanner.config import Settings

# Load journal notes
def load_journal():
    try:
        if os.path.exists("journal.json"):
            with open("journal.json", "r") as f:
                return json.load(f)
    except json.JSONDecodeError:
        st.warning("⚠️ The journal file is damaged or not in the right format. Starting with a fresh journal.")
        return {}
    except Exception as e:
        st.warning(f"⚠️ Could not load journal notes: {str(e)}")
        return {}
    return {}

# Save journal notes
def save_journal(journal):
    try:
        with open("journal.json", "w") as f:
            json.dump(journal, f)
    except Exception as e:
        st.error(f"❌ Could not save journal notes: {str(e)}")

# Portfolio storage helpers
def default_portfolio():
    return {
        "starting_cash": 10000.0,
        "cash_balance": 10000.0,
        "positions": [],
        "closed_positions": [],
        "trade_history": [],
        "balance_history": [{"date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "balance": 10000.0}],
    }


def load_portfolio():
    try:
        if os.path.exists("portfolio.json"):
            with open("portfolio.json", "r") as f:
                portfolio = json.load(f)
                portfolio.setdefault("cash_balance", portfolio.get("starting_cash", 10000.0))
                return portfolio
    except json.JSONDecodeError:
        st.warning("⚠️ The portfolio file is damaged. Starting a fresh portfolio.")
        return default_portfolio()
    except Exception as e:
        st.warning(f"⚠️ Could not load portfolio: {str(e)}")
        return default_portfolio()
    return default_portfolio()


def save_portfolio(portfolio):
    try:
        with open("portfolio.json", "w") as f:
            json.dump(portfolio, f)
    except Exception as e:
        st.error(f"❌ Could not save portfolio data: {str(e)}")


def format_currency(value):
    try:
        return f"£{value:,.2f}"
    except Exception:
        return str(value)


def format_percentage(value):
    try:
        return f"{value:+.2f}%"
    except Exception:
        return str(value)


def calculate_position_metrics(position):
    current_price = get_live_price(position["symbol"])
    quantity = position.get("quantity", 0)
    entry_price = position.get("entry_price", 0.0)
    starting_value = position.get("starting_value", entry_price * quantity)
    current_value = current_price * quantity
    if position.get("direction") == "SELL":
        unrealised_pnl = starting_value - current_value
    else:
        unrealised_pnl = current_value - starting_value
    unrealised_pct = (unrealised_pnl / starting_value * 100) if starting_value else 0.0

    return {
        "current_price": current_price,
        "current_value": current_value,
        "unrealised_pnl": unrealised_pnl,
        "unrealised_pct": unrealised_pct,
        "starting_value": starting_value,
    }


def close_portfolio_position(portfolio, index, reason):
    position = portfolio["positions"].pop(index)
    current_price = get_live_price(position["symbol"])
    exit_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if position.get("direction") == "SELL":
        realised_pnl = (position.get("entry_price", 0.0) - current_price) * position.get("quantity", 0)
    else:
        realised_pnl = (current_price - position.get("entry_price", 0.0)) * position.get("quantity", 0)
    realised_pct = (realised_pnl / position.get("starting_value", 1.0) * 100) if position.get("starting_value") else 0.0
    closed_position = {
        **position,
        "exit_datetime": exit_datetime,
        "exit_price": current_price,
        "realised_pnl": realised_pnl,
        "realised_pct": realised_pct,
        "closure_reason": reason,
    }
    portfolio.setdefault("closed_positions", []).append(closed_position)
    portfolio.setdefault("trade_history", []).append({
        "symbol": position["symbol"],
        "direction": position["direction"],
        "entry_datetime": position["entry_datetime"],
        "exit_datetime": exit_datetime,
        "entry_price": position["entry_price"],
        "exit_price": current_price,
        "quantity": position["quantity"],
        "realised_pnl": realised_pnl,
        "realised_pct": realised_pct,
        "closure_reason": reason,
    })
    current_value = current_price * position.get("quantity", 0)
    portfolio["cash_balance"] = portfolio.get("cash_balance", portfolio.get("starting_cash", 10000.0)) + current_value
    save_portfolio(portfolio)
    return closed_position


def classify_asset_class(symbol):
    if '-' in symbol:
        return "Crypto"
    elif symbol in ['SPY', 'QQQ']:
        return "ETFs"
    else:
        return "Stocks"


def save_tester_feedback(entry):
    filename = "tester_feedback.csv"
    fieldnames = ["timestamp", "confused", "liked", "expected", "broke", "other_comments"]
    try:
        write_header = not os.path.exists(filename)
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(entry)
    except Exception as e:
        st.error(f"❌ Could not save tester feedback: {str(e)}")


def get_live_price(symbol):
    try:
        data = yf.download(
            symbol,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
        )

        if data.empty:
            return None 

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        latest_close = data["Close"].dropna().iloc[-1]
        return float(latest_close)

    except Exception:
        return None 


def get_default_watchlist():
    return ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "BTC-USD", "ETH-USD", "XRP", "SOL-USD"]


def build_scan_explanation(symbol, signal):
    if signal == "BUY":
        return {
            "explanation": f"This BUY signal was generated for {symbol} from the latest scan of your watchlist. It is based on the most recent pretend market data available in this session.",
            "why_appeared": "The system found stronger supporting patterns than opposing ones for this asset.",
            "what_could_go_wrong": "Market conditions change and this pretend signal is not a guarantee. Always treat it as practice.",
            "what_to_check": "Review the asset, check your watchlist composition, and think about whether the signal matches your own study."
        }
    elif signal == "SELL":
        return {
            "explanation": f"This SELL signal was generated for {symbol} from the latest scan of your watchlist. It is based on the most recent pretend market data available in this session.",
            "why_appeared": "The system found more reasons to caution this asset than to increase exposure.",
            "what_could_go_wrong": "Prices may still move higher before reversing. This pretend signal is for learning, not for actual trading.",
            "what_to_check": "Review recent price action, support levels, and whether the asset still fits your paper trading goals."
        }
    else:
        return {
            "explanation": f"This HOLD signal was generated for {symbol} from the latest scan of your watchlist. It is based on the most recent pretend market data available in this session.",
            "why_appeared": "The system did not find a clear direction, so it suggests waiting and watching.",
            "what_could_go_wrong": "The market may move quickly after this signal, so it is important to stay aware.",
            "what_to_check": "Watch the asset for new developments, and keep your study focused on trend strength and risk."
        }

def convert_real_signal_to_dashboard_signal(real_signal):
    record = real_signal.to_record()

    confidence = record.get("score", record.get("confidence", 0))
    if confidence <= 1:
        confidence = confidence * 100

    reasons = record.get("reasons", "")
    trade_idea = record.get("trade_idea", "")

    explanation = trade_idea or "The real scanner found something worth watching."

    return {
        "symbol": record.get("symbol", "UNKNOWN"),
        "signal": "WATCH",
        "confidence": round(confidence, 1),
        "explanation": explanation,
        "timestamp": record.get("timestamp", ""),
        "why_appeared": reasons or "The scanner detected market activity worth reviewing.",
        "what_could_go_wrong": "Market conditions can change quickly. This signal is not a guarantee and should not be used on its own.",
        "what_to_check": "Check the explanation, confidence, price movement, risk/reward, stop loss, and recent market context before making any decision.",
    }
def generate_signal_for_symbol(symbol):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    seed = abs(hash(symbol)) % 100
    momentum = (seed + datetime.now().hour * 3 + datetime.now().minute) % 100

    if momentum >= 70:
        signal = "BUY"
    elif momentum >= 35:
        signal = "HOLD"
    else:
        signal = "SELL"

    confidence = max(45, min(95, momentum + (10 if signal == "BUY" else -5 if signal == "SELL" else 0)))
    messages = build_scan_explanation(symbol, signal)

    return {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "explanation": messages["explanation"],
        "timestamp": now,
        "why_appeared": messages["why_appeared"],
        "what_could_go_wrong": messages["what_could_go_wrong"],
        "what_to_check": messages["what_to_check"],
    }


def calculate_performance_metrics(history):
    total_signals = len(history)
    if total_signals == 0:
        return {"total_signals": 0, "win_rate": 0.0, "total_return": 0.0}

    watch_signals = sum(1 for s in history if s.get("signal") == "WATCH")
    win_rate = watch_signals / total_signals * 100
    return {"total_signals": total_signals, "win_rate": win_rate, "total_return": 0.0}


def run_scan(watchlist, history):
    valid_watchlist = [s.strip().upper() for s in (watchlist or []) if isinstance(s, str) and s.strip()]
    st.session_state.test_watchlist = valid_watchlist
    try:
        settings = Settings(watchlist=valid_watchlist)
        # settings.watchlist = valid_watchlist
        real_signals = real_run_scan(settings=settings, send_alerts=False)
        new_signals = [convert_real_signal_to_dashboard_signal(signal) for signal in real_signals]
    except Exception as e:
        st.error(f"Real scanner failed: {str(e)}")
        new_signals = []
    new_history = history + new_signals
    performance = calculate_performance_metrics(new_signals)
    return new_signals, new_history, performance


# Initial scan state

def load_initial_state():
    watchlist = get_default_watchlist()
    return [], [], watchlist, {"total_signals": 0, "win_rate": 0.0, "total_return": 0.0}


# Legacy demo/static data loader (unused in normal operation)
def load_mock_data():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signals = [
        {"symbol": "AAPL", "signal": "BUY", "confidence": 85, "explanation": "This BUY signal was triggered because the stock price has shown a strong upward trend over the last 5 trading days, with an average daily increase of 2.5%. High trading volume (above average by 30%) indicates strong investor interest and conviction. Technical indicators like the Relative Strength Index (RSI) at 65 suggest the stock is not overbought yet, and the Moving Average Convergence Divergence (MACD) shows bullish momentum. These factors combined contribute to the high 85% confidence score.", "timestamp": current_time, "why_appeared": "The signal appeared because Apple's stock has been rising steadily, with more people buying shares (high volume). Indicators show it's not too expensive yet and momentum is positive.", "what_could_go_wrong": "The stock could drop if bad news comes out, like poor earnings or economic slowdown. Overconfidence in the trend might lead to a sudden reversal.", "what_to_check": "Check recent news about Apple, overall market trends, and if the price is still rising. Look at Apple's financial reports and compare with competitors."},
        {"symbol": "GOOGL", "signal": "SELL", "confidence": 70, "explanation": "This SELL signal was triggered due to the stock being in an overbought condition, with the RSI reaching 75, which often precedes a price correction. The price has risen sharply in the past week (up 8%), but volume has been declining, suggesting weakening momentum. The MACD indicator is showing signs of divergence, and support levels are being tested. These bearish signals contribute to the 70% confidence score.", "timestamp": current_time, "why_appeared": "The signal appeared because Google's stock has risen too fast and too high, making it 'overbought.' Volume is dropping, meaning less buying interest, and indicators suggest a possible price drop.", "what_could_go_wrong": "If the stock keeps rising despite the signals, you might miss out on gains. Or, if news improves, the sell signal could be wrong.", "what_to_check": "Check Google's latest earnings, any regulatory news, and market sentiment. See if the price has started falling and monitor volume."},
        {"symbol": "TSLA", "signal": "HOLD", "confidence": 60, "explanation": "This HOLD signal indicates the stock is in a consolidation phase with no clear directional bias. The price has been moving sideways for the past 10 days, with low volatility. Volume is average, and technical indicators like RSI (around 50) and MACD are neutral. While there are some positive news mentions, the lack of strong momentum keeps the confidence at 60%.", "timestamp": current_time, "why_appeared": "The signal appeared because Tesla's stock isn't clearly going up or down—it's stuck in a range. No strong trends or news driving big changes.", "what_could_go_wrong": "Holding might mean missing opportunities if the stock suddenly moves. Or, if it drops, you could have sold earlier.", "what_to_check": "Check Tesla's production numbers, Elon Musk's tweets, and electric vehicle market news. Watch for any big announcements that could change direction."},
    ]
    history = signals + [
        {"symbol": "MSFT", "signal": "BUY", "confidence": 90, "explanation": "This BUY signal was triggered by a breakout above key resistance levels, with the stock closing above its 200-day moving average. Volume spiked 50% above average, confirming the move. RSI at 55 shows room for upside, and earnings reports were positive. These strong fundamentals and technicals contribute to the 90% confidence.", "timestamp": current_time, "why_appeared": "The signal appeared because Microsoft's stock broke through a key price level with high buying volume. Earnings were good, and indicators show potential for growth.", "what_could_go_wrong": "Competition or economic issues could hurt Microsoft. High confidence might lead to overbuying if the breakout fails.", "what_to_check": "Check Microsoft's quarterly results, cloud computing trends, and competitor performance. Ensure the breakout is sustained."},
        {"symbol": "AMZN", "signal": "SELL", "confidence": 75, "explanation": "This SELL signal was triggered as the stock failed to break above resistance, leading to a rejection candle. Volume was high but selling pressure increased. RSI at 70 indicates overbought conditions, and MACD histogram is declining. Recent news about regulatory scrutiny added to the bearish outlook, scoring 75% confidence.", "timestamp": current_time, "why_appeared": "The signal appeared because Amazon's stock couldn't break higher, with more selling than buying. Regulatory news and indicators suggest it's overpriced.", "what_could_go_wrong": "If regulations ease or e-commerce booms, the stock could rise anyway. Selling too early might mean missing rebounds.", "what_to_check": "Check Amazon's sales data, regulatory updates, and online shopping trends. Monitor if selling pressure continues."},
    ]
    watchlist = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]
    performance = {"total_signals": 10, "win_rate": 75.0, "total_return": 12.5}
    return signals, history, watchlist, performance

# Load data
try:
    signals, history, watchlist, performance = load_initial_state()
    journal = load_journal()
except Exception as e:
    st.error(f"❌ Error loading dashboard data: {str(e)}")
    st.info("Please refresh the page or restart the app.")
    st.stop()

if "signals" not in st.session_state:
    st.session_state.signals = signals
if "history" not in st.session_state:
    st.session_state.history = history
if "watchlist" not in st.session_state:
    st.session_state.watchlist = watchlist
if "performance" not in st.session_state:
    st.session_state.performance = performance
if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
if "feedback_saved" not in st.session_state:
    st.session_state.feedback_saved = False
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

signals = st.session_state.signals
history = st.session_state.history
watchlist = st.session_state.watchlist
performance = st.session_state.performance
portfolio = st.session_state.portfolio

# App title
st.title("Codex Market Scanner")

st.markdown("""
<div style="background:#e8f4ff; padding:20px; border-radius:10px;">

<h3>🧪 Research Mode</h3>

<p>Welcome back.</p>

<p>Codex is currently running in paper trading mode.</p>

<p>Today's scans are designed to help you learn, explore ideas and build confidence in the markets.</p>

<p><strong>No real trades will be placed.</strong></p>

<p>Take your time, stay curious, and remember that every scan is an opportunity to learn.</p>

</div>
""", unsafe_allow_html=True)

st.subheader("Start a New Scan")

st.write("Ready to see what today's markets are doing? ")

if st.button("🔍 Scan Markets", type="primary", use_container_width=True, key="top_scan_button"):
    with st.spinner("🔄 Scanning markets... Please wait."):
        st.session_state.signals, st.session_state.history, st.session_state.performance = run_scan(
            st.session_state.watchlist,
            st.session_state.history
            )
    st.write(datetime.now(ZoneInfo("Europe/London")))
    st.session_state.last_scan_time = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")
    st.success(f"Scan completed! Latest scan time: {st.session_state.last_scan_time}")
    st.rerun()
if "test_watchlist" in st.session_state:
    st.info(f"Real scanner test watchlist: {st.session_state.test_watchlist}")
# Latest scan timestamp
if st.session_state.last_scan_time:
    st.subheader(f"Latest Scan: {st.session_state.last_scan_time}")
    st.write("**What is this?** This is the date and time when you last clicked 'Scan Markets'. It tells you how fresh the signals are. If it's old, the market may have changed since then.")
else:
    st.subheader("Latest Scan: No scans run yet")
    st.info("Click 'Scan Markets' below to see the latest market signals and update this timestamp.")

st.info("This is an early demo version for learning. Scan results are generated from the current watchlist and pretend market data only. No broker is connected and no live trading is included.")

st.markdown(
    """
    <div style="background-color:#e8f4ff; padding:16px; border-radius:8px; text-align:center;">
    <h2>📚 Learn With Codex</h2>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("""
<div style='background-color:#e8f4ff; padding:16px; border-radius:8px; text-align:center;'>
<h3>⭐ New User? Read these first.</h2>
</div>
""", unsafe_allow_html=True)
st.subheader("🌱 Start here")

st.markdown(
    """
    If you're new to investing, begin with Foundations 1 - 8.

    These explain what Codex is doing, what the signals mean, and how to interpret your results.  

    After that, return whenever you'd like to explore a topic in more detail. 
    """
)

st.divider()

with st.expander("🌱 Foundation 1"):

    st.subheader("What does Codex actually do?")

    st.write("⏱ 30 second read")

    st.write(
        "Codex scans every stock and cryptocurrency on your watchlist looking for interesting market behaviour.")

    st.write(
        "It does not buy or sell anything, and a signal is not an instruction. "
        "Codex gives you a starting point for further learning and research."
    )    

    st.markdown("""
        <div style="
        background-color:#f4f8ec;
        border-left:4px solid #8aae5a;
        padding:14px 16px;
        border-radius:8px;
        margin-top:12px;
        margin-bottom:12px;
    ">
        <strong>💡 Remember</strong><br><br>
        Codex doesn't tell you what to buy.<br><br>
        It helps you decide what deserves a closer look.
        </div>
        """,
        unsafe_allow_html=True,
        )


st.divider()

with st.expander("🌱 Foundation 2"):
    st.subheader("What happens when I press Scan Markets?")

    st.markdown("""
    ⏱ 45 second read


    When you press Scan Markets, Codex checks every stock and 
    cryptocurrency on your current watchlist.


    It then looks for patterns or market activity that may deserve 
    a closer look and creates a signal if it finds something interesting.
    """)


st.markdown("""
<p style="
    color:#8AAE5A;
    font-size:13px;
    font-weight:600;
    letter-spacing:0.5px;
    margin-bottom:6px;
">

</p>
""", unsafe_allow_html=True)

st.divider()

with st.expander("🌱 Foundation 3"):
    st.subheader ("What do BUY, SELL and HOLD really mean? ")
    st.write("⏱ 1 minute read")

    st.markdown("""

    | Signal | What it means |
    |--------|---------------|
    | 🟢 **BUY** | Codex thinks this asset currently looks interesting. |
    | 🔴 **SELL** | Codex thinks this asset currently looks weak. |
    | ⚪ **HOLD** | Codex can't currently see a strong Buy or Sell opportunity. |
    """)

    st.markdown("""
    Signals are not instructions.  

    They can be wrong.  

    They are designed to help you learn and investigate ideas.

    The signal reflects what Codex thinks **right now.** It can change as markets move
    """)

st.markdown("""
<p style="
    color:#8AAE5A;
    font-size:13px;
    font-weight:600;
    letter-spacing:0.5px;
    margin-bottom:6px;
">
</p>
""", unsafe_allow_html=True)

st.divider()

with st.expander("🌱 Foundation 4"):
    st.subheader("Why isn't this financial advice? ")
    st.write("⏱ 1 minute read")

    st.markdown("""
Investing always involves uncertainty.

No scanner, expert or computer can predict the future with complete accuracy.

Codex analyses market data and highlights assets that may be worth investigating, but it never tells you what you should buy or sell.

Every investment decision should be based on **your own research,** goals and attitude to risk.

Think of Codex as a research assistant rather than as an adviser.
""")
    st.markdown(
        """
        <div style="
            background-color:#f4f8ec;
            border-left:4px solid #8aae5a;
            padding:14px 16px;
            border-radius:8px;
            margin-top:12px;
            margin-bottom:12px;
        ">
            <strong>💡 Remember</strong><br><br>
            Signals are a starting point, not a final decision.<br><br>
            Always spend a few minutes understanding why a signal appeared before taking any action.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("🔍 That's why Codex explains every signal")

    st.markdown(
        """
Instead of simply saying BUY or SELL, Codex is designed to explain:

- why the signal appeared
- which indicators contributed
- what those indicators mean
- what you might want to check next

The goal isn't to replace your judgement.

The goal is to help you become a more confident investor over time.
        """
    )

st.divider()


with st.expander("🌱 Foundation 5"):

    st.subheader("What should I do after a scan?")
    st.write("⏱️ 1 minute read")

    st.markdown("""
Treat every scan like a mini investigation.

You don't need to buy or sell anything immediately.


Work through this checklist:

☐ Read the signal first.

☐ Click **"Explain this Signal"**

☐ Look at the indicators.

☐ Decide whether it's worth investigating further.

☐ Open a Pretend Trade if you want to practise.

☐ Come back later and compare the outcome.
""")

    st.markdown(
        """
        <div style="
            background-color:#f4f8ec;
            border-left:4px solid #8aae5a;
            padding:14px 16px;
            border-radius:8px;
            margin-top:12px;
            margin-bottom:12px;
        ">
            <strong>💡 Remember</strong><br><br>
            Not every scan leads to a trade.<br><br>
            Sometimes the best decision is simply to learn why a signal appeared.<br><br>
            Every scan—whether you trade or not—is another step towards becoming a more confident investor. <br><br>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()



with st.expander("🌱 Foundation 6"):

    st.subheader("Confidence doesn't mean certainty")
    st.write("⏱️ 45 second read")

    st.markdown("""
| ❌ Wrong mindset | ✅ Better mindset |
|-----------------|------------------|
| BUY means guaranteed profit | BUY means conditions currently look promising. |
| SELL means panic | SELL means conditions currently look weaker. |
| HOLD means useless | HOLD means nothing stands out right now. |

A BUY signal is never a promise.

It's simply Codex saying:

**"This might be worth a closer look."**
""")

    st.markdown(
        """
<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
">

<strong>💡 Remember</strong><br><br>

A good investor doesn't ask,
<strong>"Will this definitely go up?"</strong><br>

They ask,<br>

<strong>"Does this deserve a closer look?"</strong>

</div>
""",
        unsafe_allow_html=True,
    )

st.divider()

with st.expander("🌱 Foundation 7"):
     st.subheader("Common beginner mistakes")
     st.write("⏱️ 45 second read")



     st.markdown("""
     <div style="
        background-color:#f4f8ec;
        border-left:4px solid #8aae5a;
        padding:14px 16px;
        border-radius:8px;
        margin-top:12px;
        margin-bottom:12px;
    ">
<strong>⚠ Watch out for these common traps</strong><br><br>

• Buying because of **one** signal instead of looking at the bigger picture.

• Ignoring how much you could lose.

• Chasing yesterday's winners because they've already gone up.

• Making decisions based on excitement or fear. 

• Expecting every trade to be profitable. 
    </div>
    **💡 Remember**<br><br>
    Even experienced investors make losing trades.<br><br>
    The goal isn't to be right every time.<br><br>
    The goal is to make thoughtful decisions over and over again.
    """,
    unsafe_allow_html=True,
)

st.divider()

with st.expander("🌱 Foundation 8"):
     st.subheader("Questions to ask before opening a trade")
     st.write("⏱️ 45 second read")

     st.markdown("""
Before opening a trade ask yourself...

□ Why did Codex highlight this?

□ Do I understand the signal?

□ Am I buying because of evidence or excitement?

□ What would make me change my mind?

□ Am I comfortable with how much could I lose?

□ Would I still make this trade if Codex hadn't shown it to me?

  <div style="
        background-color:#f4f8ec;
        border-left:4px solid #8aae5a;
        padding:14px 16px;
        border-radius:8px;
        margin-top:12px;
        margin-bottom:12px;
    ">
    <strong>💡 Remember</strong><br><br>
    You don't have to trade every opportunity.<br><br>
    Sometimes the smartest decision is to close the app, keep learning, and wait for a setup you truly understand.
    """,
    unsafe_allow_html=True,
)

st.divider()


st.subheader("🚀 Quick Start")
st.write("⏱ 30 second read")

st.markdown("""
**Ready to try Codex?**
Here's the simplest way to use it for the first time.
""")

st.divider()

st.markdown("""
**Step 1**

🔍 Press **Scan Markets**

Let Codex check every stock and cryptocurrency on your watchlist.
""")

st.divider()

st.markdown("""
**Step 2**

📊 Open one interesting signal

Don't worry about finding the "perfect" trade.

Just pick one that catches your attention.
""")

st.divider()

st.markdown("""
**Step 3**

🧠 Click **Explain this Signal**

Read why Codex generated the signal and which indicators contributed.
""")

st.divider()

st.markdown("""
**Step 4**

📈 Decide whether it's worth investigating further

Remember, a signal is an invitation to learn - not an instruction to trade.
""")

st.divider()

st.markdown("""
**Step 5**

🎮 Open a Pretend Trade

Practise first.

Watch what happens without risking any real money, then compare what actually happened with what Codex suggested.
""")

st.divider()

st.markdown(
    """

<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
    ">
    <strong>💡 Remember</strong><br><br>
    The goal isn't to find your first winning trade. <br><br>
    The goal is to understand why Codex found the opportunity. 
    """,
    unsafe_allow_html=True,
)
st.write("**🌱 After a few Pretend Trades, you'll naturally start recognising patterns and your confidence will grow naturally.**")


st.divider()

st.markdown("""
<div style='background-color:#e8f4ff; padding:16px; border-radius:8px; text-align:center;'>
<h3>📘 Learn the Language</h2>
</div>
""", unsafe_allow_html=True)

st.subheader("What is a Signal?")
buy_tab, sell_tab, hold_tab = st.tabs(
    ["🟢 BUY", "🔴 SELL", "⚪ HOLD"]
)
with buy_tab:
        st.markdown("""
### 🟢 BUY

A BUY signal does **not** mean:

**"Buy this immediately."**

It means Codex has noticed something that may be worth investigating further.

Before making a decision, ask yourself:

- why the signal appeared
- which indicators contributed
- whether the opportunity still makes sense to you
- how much you could afford to lose

A BUY signal is a starting point, not a promise.
""")

with sell_tab:
    st.markdown("""
### 🔴 SELL

A SELL signal does **not** mean:

**"Sell immediately."**

It means Codex has noticed that market conditions currently look weaker than before.

That may be worth investigating, but it does not automatically mean the asset will keep falling.

Check the explanation, look at what changed, and make your own decision.
""")

with hold_tab:
    st.markdown("""
### ⚪ HOLD

A HOLD signal means Codex cannot currently see a strong reason to buy or sell.

That is not a useless result.

Sometimes nothing clearly stands out, and waiting is the most sensible option.

**Codex would rather say "nothing interesting right now" than pretend it knows what will happen next.**
""")

st.divider()


st.subheader("What is a Watchlist?")
st.markdown("""
A watchlist is simply a list of stocks or cryptocurrencies you want the scanner to check.  
Think of it as a favourites list.  
""")

st.divider()

st.subheader("What is a Pretend Trade?")
st.write("A Pretend Trade lets you practice buying and selling without risking real money. It helps you learn how the scanner works before making real investing decisions.")

st.divider()

st.subheader("What is Paper Trading?")
st.write("Paper Trading means practising investing without using real money.")
st.write("You can open pretend trades, track how they perform, and learn how the scanner works without risking any real money.")
st.write("It is designed to help beginners build confidence before making real investing decisions")

st.divider()

st.subheader('What is "Explain This Signal"?')

st.markdown("""
**Explain This Signal** helps you understand why Codex generated a particular BUY, SELL or HOLD signal.

It shows:

- what Codex noticed
- which indicators contributed
- what those indicators mean
- what you may want to investigate next

It does not tell you what decision to make.

It gives you the evidence behind the signal so you can make your own informed decision.
""")

st.divider()

st.subheader("What is a Portfolio?")
st.markdown("""
A Portfolio is where Codex keeps all of your Pretend Trades. 

Your Portfolio helps you:

- see whether your ideas would have made or lost money
- compare different trades over time
- learn which types of opportunities you understand best
- build confidence before risking real money

Your Portfolio isn't about making the biggest profit. 

It's about becoming a better investor one trade at a time.
"""
)

st.divider()

st.markdown("""
<div style='background-color:#e8f4ff; padding:16px; border-radius:8px; text-align:center;'>
<h3>📈 Learn by Example</h2>
</div>
""", unsafe_allow_html=True)

st.subheader("Understanding Signal Types")

buy_tab, sell_tab, hold_tab = st.tabs(
    ["🟢 BUY Example", "🔴 SELL Example", "⚪ HOLD Example"]
)
with buy_tab:
    st.subheader("🟢 BUY Example")

    st.markdown("""
1️⃣ What Codex saw

Codex found several indicators becoming stronger at the same time.

That made this asset worth highlighting for further investigation.
""")

    st.divider()

    st.write("2️⃣ What this DOESN'T mean")

    st.markdown(
    """
<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
">
<strong>💡 Remember</strong><br><br>
A BUY signal is <strong>not</strong> saying:<br><br>
<strong>"This will definately go up."</strong><br><br>
It is saying:<br><br>
<strong>"This deserves a closer look."</strong>

</div>
""",
unsafe_allow_html=True,
)

    st.write("3️⃣ What should you do next?")

    st.markdown("""
- Read **Explain This Signal**
- Look at which indicators contributed
- Decide whether the explanation makes sense to you
- Think about how much you could afford to lose
- Only then decide whether it deserves further investigation
""")

    st.write("4️⃣ What did you learn?")

    st.markdown("""
Even if you decide **not** to open a Pretend Trade, the example has still been useful.

You have practised reading a signal, checking the evidence and making your own decision.
""")

with sell_tab:
    st.subheader("🔴 SELL Example")

    st.markdown("""
1️⃣ What Codex saw

Codex noticed several indiciators becoming weaker at the same time. 

That made this asset worth highlighting for further investigation. 
""")

    st.divider()

    st.write("2️⃣ What this DOESN'T mean")

    st.markdown(
    """
<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
">
<strong>💡 Remember</strong><br><br>
A SELL signal is <strong>not</strong> saying:<br><br>
<strong>"Sell everything immediately."</strong><br><br>
It is saying:<br><br>
<strong>"Conditions currently look weaker."</strong>

</div>
""",
unsafe_allow_html=True,
)

    st.write("3️⃣ What should you do next?")

    st.markdown("""
- Read **Explain This Signal**
- Look at which indicators weakened.
- Decide whether the change makes sense.
- Think about your own investment plan.
- Only then decide whether any action is appropriate.
""")

    st.write("4️⃣ What did you learn?")

    st.markdown("""
Even if you decide to do nothing...

....you've practised recognising when conditions become weaker instead of reacting emotionally.

""")

with hold_tab:
    st.subheader("⚪ HOLD Example")

    st.markdown("""
1️⃣ What Codex saw

None of the indicators were strong enough to produce a Buy or Sell signal. 

Nothing particularly interesting stood out. 
""")

    st.divider()

    st.write("2️⃣ What this DOESN'T mean")

    st.markdown(
    """
<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
">
<strong>💡 Remember</strong><br><br>
A HOLD signal is <strong>not</strong> saying:<br><br>
<strong>"This asset is bad."</strong><br><br>
It is saying:<br><br>
<strong>"Nothing stands out right now."</strong>

</div>
""",
unsafe_allow_html=True,
)

    st.write("3️⃣ What should you do next?")

    st.markdown("""
- Read the explanation anyway.
- Notice why nothing triggered. 
- Compare it with Buy and Sell examples. 
- Learn what "normal" looks like.
""")

    st.write("4️⃣ What did you learn?")

    st.markdown("""
Sometimes the best investing decision...

...is simply waiting. 

Learning when **not** to trade is just as important as learning when to investigate further. 
""")


st.divider( )

first_tab, losing_tab = st.tabs(
    ["🎮 Learning with Winning Trades", "📉 Learning with Losing Trades"]
)
with first_tab:
    st.subheader("🎮 Following a Pretend Trade")
    st.write("Opening your First Pretend Trade...")

    st.write("**1️⃣ What happened?**")

    st.markdown("""
    You decided this BUY signal looked interesting.

    Instead of risking real money...

    ...you opened a Pretend Trade. 
    """)

    st.divider()
    
    st.write("**2️⃣ What happens next?**")
    st.markdown("""

    Codex now watches the price. 

    Every day you'll be able to see:

    - whether your idea improved
    - whether it weakened
    - what happened after the signal appeared
    """)

    st.divider()

    st.write("**3️⃣ What should you learn?**")
    st.markdown("""

    Don't judge yourself by profit.

    Instead ask:

    - Did I understand the signal?
    - Did I notice the risks?
    - Would I make the same decision again?
    """)

    st.divider()

    st.write("**4️⃣ Why is this useful?**")
    st.markdown("""

    By repeating this process...

    you'll gradually begin recognising good opportunities yourself. 
        """)

    st.subheader("⭐ Big Lesson")
    st.markdown("""
    **The goal isn't to make pretend money.**

    It's to practice recognising opportunities, understsanding signals and building confidence before risking real money. 
    """)

    st.divider()


with losing_tab:

    st.subheader("📉 Learning from a Pretend Trade")

    st.write("**1️⃣ What happened?**")

    st.markdown("""
You opened a Pretend Trade because the BUY signal looked promising.

But this time...

...the price moved down instead of up.
""")

    st.divider()

    st.write("**2️⃣ What happens next?**")

    st.markdown("""
Codex keeps tracking the trade.

Now you can see:

- how much it fell
- whether the signal eventually recovered
- whether selling earlier or waiting longer would have helped
""")

    st.divider()

    st.write("**3️⃣ What should you learn?**")

    st.markdown("""
Don't think:

"I failed."

Instead ask yourself:

- Did I understand why the signal appeared?
- Did I manage the risk sensibly?
- Would I make the same decision again?
- What can this trade teach me?
""")

    st.divider()

    st.write("**4️⃣ Why is this useful?**")

    st.markdown("""
Every experienced investor has losing trades.

Paper Trading lets you experience them...

...without losing real money.

Sometimes the trades that don't work out teach you the most.
""")

    st.subheader("⭐ Big Lesson")
    st.markdown("""
    **The goal isn't to avoid losing trades.**
    
    The goal is to become someone who understands why trades win or lose.
    
    That's how confident investors are built.
    """)


st.markdown(
"""
<div style="
    background-color:#f4f8ec;
    border-left:4px solid #8aae5a;
    padding:14px 16px;
    border-radius:8px;
    margin-top:12px;
    margin-bottom:12px;
">
<h3 style="margin-top:0; margin-bottom:18px;">
✅ Before you move onto real money, ask yourself...
</h3>


<li>Do I understand what BUY means?</li>
<li>Do I understand what SELL means?</li>
<li>Do I know a signal is not a guarantee?</li>
<li>I've practised with Pretend Trades.</li>
<li>I've seen both winning and losing trades.</li>
<li>Do I know why risk management matters?</li>
</ul>

<br>
<strong>If not....that's completely ok</strong><br><br>

Keep practising.

Confidence comes from understanding - not rushing.


</div>
""",
unsafe_allow_html=True,
)

st.divider()

st.markdown("""
<div style='background-color:#e8f4ff; padding:16px; border-radius:8px; text-align:center;'>
<h3>⭐ Understanding your Dashboard ⭐</h2>
</div>
""", unsafe_allow_html=True)



# App title
st.markdown("""
**Welcome!** This dashboard helps beginners like you understand market signals.  
It shows buy/sell/hold recommendations for stocks based on data analysis.  
The sections below explain each part of the dashboard in plain English.  
""")

# Disclaimer reminder
st.warning("This tool is educational only, paper trading only, and does not connect to a broker. Always do your own research before using real money.")


# Performance summary cards
st.subheader("📍 Your Dashboard at a Glance")
st.markdown("""
These three numbers give you a quick snapshot of what the scanner has found so far.  
These numbers describe the latest scan results, not how much money you have made or lost.
- Latest Scan Signals tells you how many Buy, Sell, or Hold signals were found in the most recent scan.
- Watch Signal Rate tells you what percentage of the latest scan results were worth reviewing.
- Total Return will become more useful once the pretend trading feature has been developed further.  
""")
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("🟢 Latest Scan Signals")
        st.write("")
        st.metric("", performance["total_signals"])

        st.markdown("""

    **What is it?**

    The number of Buy, Sell and Hold signals found in the most recent scan.

    **Why does it matter?**

    More signals means more opportunities to investigate.

    **What should I do?**

    Open the signals and read why Codex highlighted them.
    """)

with col2:
    with st.container(border=True):
        st.subheader("📈 Watch Signal Rate")
        st.write("")
        st.metric("", f"{performance['win_rate']:.1f}%")

        st.markdown("""

    **What is it?**
    The percentage of all scanned assets that Codex thought were worth investigating further. 
    
    **Why does it matter?**
    A higher percentage means more opportunities were found during the latest scan.  A lower percentage usually means the market looks quieter. 
    
    **What should I do?**
    Don't judge the market by this number alone.  Open the signals and understand why they were generated. 
    """)
with col3:
    with st.container(border=True):
        st.subheader("💰 Paper Return")
        st.write("")
        st.metric("", "Not connected yet")

        st.markdown("""
   
    **What is it?**
    The running result of your Pretend Trades once Paper Trading is fully connected. 
    
    **Why does it matter?**
    It helps you see how your decisions would have performed without risking real money.
    
    **What should I do?**
    For now, ignore this number.  Focus on learning how to recognise good opportunities before worrying about profit. 
    """)
    
st.divider()

# Charts for signals
st.subheader("📊 Reading the Charts")
st.write("**What is this chart?** This bar chart shows how many buy, sell, or hold signals were found in the latest scan of your current watchlist.")
if signals:
    signal_counts = pd.DataFrame(signals).groupby("signal").size().reset_index(name="count")
    fig = px.bar(signal_counts, x="signal", y="count", title="Signals by Type")
    st.plotly_chart(fig)
else:
    st.warning("Not enough fresh scan data yet — run more scans to build this view.")

# Confidence scores chart
st.subheader("Signal Scores")
st.write("**What is this chart?** This shows the scanner score for each latest signal. Higher scores mean the scanner found more reasons to review that asset.")
if signals:
    st.write(pd.DataFrame(signals)[["symbol", "signal", "confidence"]])
    fig2 = px.scatter(pd.DataFrame(signals), x="symbol", y="confidence", color="signal", size="confidence", title="Signal Scores")
    st.plotly_chart(fig2)
else:
    st.warning("Not enough fresh scan data yet — run more scans to build this view.")

# Market Mood Indicator
st.subheader("📊 Market Mood Indicator")
st.write("**What is this?** A simple snapshot that explains if the overall signal picture looks calm, bullish, or bearish.")

def calculate_market_mood(signals):
    if not signals or len(signals) < 2:
        return None
    try:
        buy_count = sum(1 for s in signals if s.get('signal') == 'BUY')
        sell_count = sum(1 for s in signals if s.get('signal') == 'SELL')
        hold_count = sum(1 for s in signals if s.get('signal') == 'HOLD')
        total = len(signals)
        avg_conf = sum(s.get('confidence', 50) for s in signals) / total

        if buy_count >= 2 and sell_count <= 1:
            mood = 'bullish'
            emoji = '📈'
            explanation = 'The signal picture is leaning up. This means more assets are showing buy signals than sell signals.'
        elif sell_count >= 2 and buy_count <= 1:
            mood = 'bearish'
            emoji = '📉'
            explanation = 'The signal picture is leaning down. This means more assets are showing sell signals than buy signals.'
        else:
            mood = 'calm'
            emoji = '😌'
            explanation = 'The signal picture is mixed. It is not clearly up or down, so the market looks calm or uncertain.'

        return {
            'mood': mood,
            'emoji': emoji,
            'explanation': explanation,
            'confidence': int(avg_conf),
            'buy_count': buy_count,
            'sell_count': sell_count,
            'hold_count': hold_count
        }
    except Exception as e:
        st.warning(f"⚠️ Could not calculate market mood: {str(e)}")
        return None

mood_data = calculate_market_mood(signals)
if mood_data:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Market Mood", mood_data['emoji'], help="The overall direction of current signals.")
        st.metric("Avg Confidence", f"{mood_data['confidence']}%", help="The average confidence of all signals.")
    with col2:
        st.write(f"### {mood_data['emoji']} {mood_data['mood'].capitalize()}")
        st.write(mood_data['explanation'])

    with st.expander("See how the signals add up"):
        st.write(f"- 🟢 BUY signals: {mood_data['buy_count']}")
        st.write(f"- 🔴 SELL signals: {mood_data['sell_count']}")
        st.write(f"- 🟡 HOLD signals: {mood_data['hold_count']}")
        st.write("**What you should do:**")
        st.write("- If the market is bullish, keep learning and do extra checks before paper trading.")
        st.write("- If the market is bearish, be extra careful and consider waiting.")
        st.write("- If the market is calm, take your time and watch the next signals.")
else:
    st.warning("Not enough fresh scan data yet — run more scans to build this view.")
    st.write("**Based on:** The latest scan results from your current watchlist.")

# Current Signals with explanations and color-coded confidence
st.subheader("Current Signals")
st.write("**What is this table?** This shows the latest buy/sell/hold signals for stocks. 'Symbol' is the stock ticker (like AAPL for Apple). 'Signal' is the recommendation. 'Traffic Light Label' uses colors like a traffic light: 🟢 Strong movement (good to act on), 🟡 Worth studying (check more), 🔴 High caution (be careful), 🔵 Low interest (not urgent). Read the 'explanation' for why the signal was given. 'Timestamp' is when it was created.")
def traffic_light_label(conf):
    if conf >= 90:
        return "🔴 High caution"
    elif conf >= 80:
        return "🟢 Strong movement"
    elif conf >= 60:
        return "🟡 Worth studying"
    else:
        return "🔵 Low interest"

if signals:
    signals_df = pd.DataFrame(signals)
    signals_df["Traffic Light Label"] = signals_df["confidence"].apply(traffic_light_label)
    st.dataframe(signals_df[["symbol", "signal", "Traffic Light Label", "explanation", "timestamp"]])
else:
    st.warning("Not enough fresh scan data yet — run more scans to build this view.")
    st.write("**Based on:** The latest scan results from your current watchlist.")

# Explain labels
st.write("**Traffic Light Labels Explained:**")
st.write("- **🔴 High caution:** Very high confidence (90%+). The signal is strong, but double-check because high confidence can mean high risk or overconfidence.")
st.write("- **🟢 Strong movement:** High confidence (80-89%). Good signal to consider acting on, like a green light for go.")
st.write("- **🟡 Worth studying:** Medium confidence (60-79%). Yellow light—pause and learn more before deciding.")
st.write("- **🔵 Low interest:** Low confidence (<60%). Blue light—low priority, maybe ignore or watch casually.")

st.divider()

# Explain This Signal
st.subheader("📖 Explain This Signal")
st.write("**💡 What will appear here?**")
st.markdown("""
When you run your first scan, simply click on any signal. 

Codex will explain it in plain English, including

- ✅ Why the signal appeared
- ⚠️ What could make it fail
- 🔍 What you should investigate before acting
- 📚 What you can learn from it

You don't need to understand technical indicators. 

Codex translates them into everyday language. 
""")

st.divider()

with st.expander("📘 Example Lesson — How to read a BUY signal - Click to open"):
    st.write("(Example only - this is not today's market)")

    st.divider()

    st.write("**🟢 BUY Signal**")
    st.write("**What does BUY actually mean?**")

    st.markdown("""
    It does **not** mean:

    "Go and buy this immediately"

    It means:

    "The scanner found enough positive evidence that this stock deserves a closer look
    """)

    st.divider()

    st.write("**Why did Codex notice it?**")

    st.markdown("""
    Imagine the scanner found:
    ✅ Price trend improving

    ✅ Buyers becoming stronger

    ✅ Momentum increasing

    These things together make the scanner interested
    """)

    st.divider()

    st.write("**What could go wrong?**")

    st.markdown("""
    Even good signals fail. 

    Perhaps:

    - Company news is released

    - The market suddenly falls

    - Buyers disappear

    No signal is guaranteed.
    """)

    st.divider()

    st.write("**Before opening a Pretend Trade**")

    st.markdown("""
    Ask yourself:
    Do I understand why this is a BUY?

    □ Am I following the scanner rather than guessing?

    □ What would make this signal fail?
    """)

    st.divider()

    st.write("**⭐ What should you learn?**")
    st.markdown("""
    The goal isn't to memorise indicators.

    The goal is to recognise WHY opportunities appear.
    """)

st.divider()

st.subheader("🚀 Ready?")
st.markdown("""
Run your first scan.

Choose any signal.

Codex will explain the real one.
""")


st.divider()


st.write("**What is this?** Select a signal to get a simple explanation of why it appeared, what could go wrong, and what to check before trying a paper trade. This helps beginners understand risks and do their homework.")
all_signals_for_explain = signals + history
if all_signals_for_explain:
    signal_options = [f"{s['symbol']} ({s['signal']})" for s in all_signals_for_explain]
    selected_explain = st.selectbox("Choose a signal to explain", signal_options, key="explain_select")

    if selected_explain:
        selected_data = next(
            s for s in all_signals_for_explain
            if f"{s['symbol']} ({s['signal']})" == selected_explain
            )

        signal_name = selected_data["signal"].upper()
        symbol = selected_data["symbol"]

        if signal_name == "BUY":
            signal_icon = "🟢"
        elif signal_name == "SELL":
            signal_icon = "🔴"
        else:
            signal_icon = "⚪"

        st.subheader(f"{signal_icon} {signal_name} — {symbol}")

        st.markdown("### ✅ Why Codex noticed this")
        st.write(selected_data["why_appeared"])

        st.divider()

        st.markdown("### ⚠️ What could make this fail?")
        st.write(selected_data["what_could_go_wrong"])

        st.divider()

        st.markdown("### 🔍 What should I check next?")
        st.write(selected_data["what_to_check"])
    

        st.divider()

        st.markdown("### 📚 What should I learn?")

        if signal_name == "BUY":
            st.markdown("""
            A BUY signal does not guarantee that the price will rise.

            It means Codex found enough positive evidence for this asset to deserve a closer look.
            """)

        elif signal_name == "SELL":
            st.markdown("""
            A SELL signal does not guarantee that the price will continue falling.

            It means Codex found signs that conditions currently look weaker and may deserve further investigation.
            """)

        else:
            st.markdown("""
            A HOLD signal is not a useless result.

            It means Codex cannot currently see enough evidence for a strong BUY or SELL signal.
            """)

            st.markdown("""
            The goal is not to follow the signal blindly.

            The goal is to understand why it appeared and decide whether the evidence makes sense to you.
            """)
        
    else:
        st.info("No signals are available yet. Run a scan to generate signal explanations.")

st.divider()

st.subheader("📖 Learn More")

st.markdown("""
📈 Scanner

Everything about today's scan
- Current Signals
- Explain This Signal
- Signal History

🎓 Academy

Everything about learning
- Dashboard Tour
- Reading Charts
- BUY / SELL / HOLD
- Winning Trades
- Losing Trades
- Risk Management
- Ready for Real Money

""")

# Signal history table
st.subheader("Signal History")
st.write("**What is this table?** This is a list of all past signals, including older ones. It helps you see patterns over time. Same columns as above.")
history_df = pd.DataFrame(history)
st.dataframe(history_df)

# Watchlist management
st.subheader("Watchlist")
st.write(f"📈 Watching {len(watchlist)} assets")

st.write("**What is this?** A watchlist is a list of stocks and cryptocurrencies you want to monitor. Edit the list in the text box below by typing symbols separated by commas. This helps you focus on the assets you want to practice with.")

# Initialize session state for watchlist edit
if "watchlist_edit" not in st.session_state:
    st.session_state.watchlist_edit = ", ".join(watchlist)

st.write("**How to format symbols:**")
st.write("- **Stock symbols:** Use uppercase letters, like AAPL, MSFT, NVDA")
st.write("- **Crypto symbols:** Use the format BTC-USD, ETH-USD, SOL-USD")
st.write("- **Separate symbols with commas** (example: AAPL, MSFT, BTC-USD, ETH-USD)")
st.write("- **Example list:** AAPL, MSFT, NVDA, BTC-USD, ETH-USD")

watchlist_text = st.text_area(
    "Edit your watchlist (comma-separated symbols)",
    value=st.session_state.watchlist_edit,
    height=120,
    help="Type or paste symbols here. Stocks use simple symbols like AAPL. Crypto uses symbols with -USD, like BTC-USD."
)

# Validate and parse watchlist

def validate_watchlist(text):
    if not text or not text.strip():
        return [], []

    raw_symbols = [s.strip().upper() for s in text.split(",")]
    raw_symbols = [s for s in raw_symbols if s]

    valid_symbols = []
    invalid_symbols = []
    for symbol in raw_symbols:
        if 1 <= len(symbol) <= 10 and all(c.isalnum() or c == '-' for c in symbol):
            valid_symbols.append(symbol)
        else:
            invalid_symbols.append(symbol)

    return valid_symbols, invalid_symbols

valid_symbols, invalid_symbols = validate_watchlist(watchlist_text)
st.session_state.watchlist_edit = watchlist_text

if valid_symbols:
    watchlist = valid_symbols
    st.session_state.watchlist = valid_symbols
    st.success(f"✅ Valid symbols: {', '.join(valid_symbols)}")
else:
    st.info("Enter symbols above to update your watchlist.")

if invalid_symbols:
    st.warning(f"⚠️ Invalid symbols ignored: {', '.join(invalid_symbols)}. Use letters, numbers, and hyphens only.")

if watchlist:
    st.write(f"**Your Watchlist ({len(watchlist)} items):** {', '.join(watchlist)}")
else:
    st.info("Your watchlist is empty. Add some symbols above to get started!")

# Paper Trading
st.subheader("Paper Trading")
st.write("**What is paper trading?** This is pretend trading with fake money. It lets you practice without risking real cash. Select a stock, choose buy or sell, pick how many shares, and click 'Execute Trade' to simulate. No real money is involved.")
if watchlist:
    trade_symbol = st.selectbox("Select Symbol", watchlist)
    trade_action = st.selectbox("Action", ["BUY", "SELL"])
    trade_signal_type = st.selectbox("Signal Type", ["breakout", "pullback", "unusual volume", "volatility spike", "momentum"])
    trade_quantity = st.number_input("Quantity", min_value=1, value=10)
    if st.button("Execute Trade"):
        entry_price = get_live_price(trade_symbol)
        entry_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        starting_value = entry_price * trade_quantity
        new_position = {
            "symbol": trade_symbol,
            "direction": trade_action,
            "signal_type": trade_signal_type,
            "entry_datetime": entry_datetime,
            "entry_price": entry_price,
            "quantity": trade_quantity,
            "starting_value": starting_value,
        }
        cash_balance = portfolio.get("cash_balance", portfolio.get("starting_cash", 10000.0))

        if trade_action == "BUY" and starting_value > cash_balance:
            st.error(
                f"Not enough paper cash. This trade costs {format_currency(starting_value)}, "
                f"but you only have {format_currency(cash_balance)} available."
            )
        else:
            if trade_action == "BUY":
                portfolio["cash_balance"] = cash_balance - starting_value

            portfolio["positions"].append(new_position)
            save_portfolio(portfolio)

            st.success(
                f"Simulated {trade_action} of {trade_quantity} shares of {trade_symbol} "
                f"at {format_currency(entry_price)} based on {trade_signal_type} signal"
            )
else:
    st.info("The paper trading controls below will appear after you add symbols to your watchlist.")

# Open Pretend Trades
st.subheader("Open Pretend Trades")
st.write("**What is an open trade?** This is a pretend position you have entered but not yet closed. It shows how your pretend investment is doing right now. Unrealised profit/loss is the gain or loss if you closed it at the current price.")
if portfolio["positions"]:
    for i, pos in enumerate(portfolio["positions"]):
        metrics = calculate_position_metrics(pos)
        st.write(f"**Trade {i+1}: {pos['symbol']} ({pos['direction']})**")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"Entry: {pos['entry_datetime']} at {format_currency(pos['entry_price'])}")
            st.write(f"Current: {format_currency(metrics['current_price'])}")
            st.write(f"Quantity: {pos['quantity']}")
        with col2:
            if metrics["unrealised_pnl"] > 0:
                st.success(
                    f"Unrealised P/L: {format_currency(metrics['unrealised_pnl'])} "
                    f"({format_percentage(metrics['unrealised_pct'])})"
    )
            elif metrics["unrealised_pnl"] < 0:
                st.error(
                    f"Unrealised P/L: {format_currency(metrics['unrealised_pnl'])} "
                    f"({format_percentage(metrics['unrealised_pct'])})"
    )
            else:
                st.info(
                    f"Unrealised P/L: {format_currency(metrics['unrealised_pnl'])} "
                    f"({format_percentage(metrics['unrealised_pct'])})"
    )
            st.write(f"Starting Value: {format_currency(metrics['starting_value'])}")
            st.write(f"Current Value: {format_currency(metrics['current_value'])}")
        
        closure_options = [
            "Profit target reached",
            "Loss became too large", 
            "Signal weakened",
            "Market reversed",
            "Volatility increased",
            "Wanted to lock in profits",
            "Testing strategy",
            "Emotional decision",
            "Unsure what to do",
            "Other"
        ]
        reason = st.selectbox("Why close this trade?", closure_options, key=f"reason_{i}")
        if reason == "Other":
            custom_reason = st.text_input("Enter custom reason", key=f"custom_{i}")
            reason = custom_reason if custom_reason else "Other"
        
        if st.button(f"Close This Trade", key=f"close_btn_{i}"):
            closed = close_portfolio_position(portfolio, i, reason)
            st.success(f"Closed trade for {closed['symbol']}: Realised P/L {format_currency(closed['realised_pnl'])} ({format_percentage(closed['realised_pct'])})")
            st.rerun()
        st.markdown("---")
else:
    st.info("No open pretend trades yet. Execute a trade above to get started.")

# Closed Pretend Trades
st.subheader("Closed Pretend Trades")
st.write("**What is a closed trade?** This is a pretend position you have exited. It shows the final result of your pretend investment. Realised profit/loss is the actual gain or loss from that trade. The table below also shows the reason you chose to close each trade.")
if portfolio["closed_positions"]:
    closed_trades_data = []
    for pos in portfolio["closed_positions"]:
        closed_trades_data.append({
            "Symbol": pos["symbol"],
            "Direction": pos["direction"],
            "Entry Date/Time": pos["entry_datetime"],
            "Exit Date/Time": pos["exit_datetime"],
            "Entry Price": format_currency(pos["entry_price"]),
            "Exit Price": format_currency(pos["exit_price"]),
            "Quantity": pos["quantity"],
            "Realised P/L": format_currency(pos["realised_pnl"]),
            "Realised P/L %": format_percentage(pos["realised_pct"]),
            "Closure Reason": pos.get("closure_reason", "Not recorded"),
        })
    st.dataframe(pd.DataFrame(closed_trades_data), use_container_width=True)
else:
    st.info("No closed pretend trades yet. Close an open trade to see results here.")

# Portfolio Summary
st.subheader("Pretend Portfolio Summary")
st.write("**What is this?** This shows an overview of your pretend trading performance. Unrealised profit/loss is from open trades. Realised profit/loss is from closed trades. Total return is your overall pretend gain or loss.")
starting_cash = portfolio.get("starting_cash", 10000.0)
open_count = len(portfolio["positions"])
closed_count = len(portfolio["closed_positions"])
unrealised_pnl = sum(calculate_position_metrics(pos)["unrealised_pnl"] for pos in portfolio["positions"])
realised_pnl = sum(pos.get("realised_pnl", 0.0) for pos in portfolio["closed_positions"])
total_value = portfolio.get("cash_balance", starting_cash) + sum(calculate_position_metrics(pos)["current_value"] for pos in portfolio["positions"])
total_return_pct = ((total_value - starting_cash) / starting_cash * 100) if starting_cash else 0.0
portfolio.setdefault("balance_history", [])

latest_balance = portfolio["balance_history"][-1] if portfolio["balance_history"] else None

if latest_balance is None or latest_balance.get("balance") != total_value:
    portfolio["balance_history"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "balance": total_value,
    })
    save_portfolio(portfolio)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Open Trades", open_count)
    st.metric("Closed Trades", closed_count)
with col2:
    st.metric("Total Portfolio Value", format_currency(total_value))
    st.metric("Unrealised P/L", format_currency(unrealised_pnl))
with col3:
    st.metric("Realised P/L", format_currency(realised_pnl))
    st.metric("Total Return %", format_percentage(total_return_pct))

# Performance Analytics
st.subheader("Performance Analytics")
st.write("**What is this?** This section shows detailed stats on your pretend trading performance. It helps you understand how well your pretend trades are doing overall.")
st.write("**Important reminders:** These are simulated paper trading results only. Past pretend performance doesn't predict future real results. Small numbers of trades are unreliable. This is educational only, not financial advice. Real trading has costs, delays, emotions, and risk.")

# Calculate additional metrics
if closed_count > 0:
    winning_trades = [pos["realised_pnl"] for pos in portfolio["closed_positions"] if pos["realised_pnl"] > 0]
    losing_trades = [pos["realised_pnl"] for pos in portfolio["closed_positions"] if pos["realised_pnl"] < 0]
    win_rate = len(winning_trades) / closed_count * 100
    avg_winning_trade = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
    avg_losing_trade = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0
    best_trade = max(pos["realised_pnl"] for pos in portfolio["closed_positions"])
    worst_trade = min(pos["realised_pnl"] for pos in portfolio["closed_positions"])
else:
    win_rate = 0.0
    avg_winning_trade = 0.0
    avg_losing_trade = 0.0
    best_trade = 0.0
    worst_trade = 0.0

cash_balance = portfolio.get("cash_balance", starting_cash)
money_invested = sum(calculate_position_metrics(pos)["current_value"] for pos in portfolio["positions"])
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Starting Pretend Balance", format_currency(starting_cash))
    st.write("**Starting pretend balance:** The fake money you began with (£10,000).")
    st.metric("Available Cash", format_currency(cash_balance))
    st.write("**Available cash:** Fake money not currently tied up in open trades.")
    st.metric("Current Pretend Portfolio Value", format_currency(total_value))
    st.write("**Current pretend portfolio value:** Your total fake money now, including open trades.")
    st.metric("Total Pretend Profit/Loss", format_currency(total_value - starting_cash))
    st.write("**Total pretend profit/loss:** How much your fake money has changed overall.")
with col2:
    st.metric("Total Return %", format_percentage(total_return_pct))
    st.write("**Total return %:** The percentage change in your fake money.")

    st.metric("Money Invested", format_currency(money_invested))
    st.write("**Money invested:** Current value of your open pretend trades.")

    st.metric("Realised Profit/Loss", format_currency(realised_pnl))
    st.write("**Realised profit/loss:** Gains or losses from closed pretend trades.")
    st.metric("Unrealised Profit/Loss", format_currency(unrealised_pnl))
    st.write("**Unrealised profit/loss:** Potential gains or losses from open pretend trades.")
with col3:
    st.metric("Number of Open Trades", open_count)
    st.write("**Number of open trades:** Pretend positions you haven't closed yet.")
    st.metric("Number of Closed Trades", closed_count)
    st.write("**Number of closed trades:** Pretend positions you've finished.")
    st.metric("Win Rate %", f"{win_rate:.1f}%")
    st.write("**Win rate:** Percentage of closed trades that closed with a profit. Break-even trades are not counted as wins.")
    st.metric("Average Winning Trade", format_currency(avg_winning_trade))
    st.write("**Average winning trade:** Average profit from trades that made money.")
    st.metric("Average Losing Trade", format_currency(avg_losing_trade))
    st.write("**Average losing trade:** Average loss from trades that lost money.")
    st.metric("Best Trade", format_currency(best_trade))
    st.write("**Best trade:** The biggest profit from a single closed trade.")
    st.metric("Worst Trade", format_currency(worst_trade))
    st.write("**Worst trade:** The biggest loss from a single closed trade.")

# Performance Charts
st.subheader("Performance Charts")
st.write("**What are these charts?** Simple graphs showing your pretend trading performance over time and by category.")

# Portfolio value over time
if portfolio["balance_history"]:
    balance_df = pd.DataFrame(portfolio["balance_history"])
    balance_df["date"] = pd.to_datetime(balance_df["date"])
    fig = px.line(balance_df, x="date", y="balance", title="Pretend Portfolio Value Over Time")
    st.plotly_chart(fig)
    st.write("**Portfolio value over time:** Shows how your total fake money changed. Up means gains, down means losses.")

# Realised P/L over time (cumulative)
if portfolio["closed_positions"]:
    realised_over_time = []
    cumulative = 0
    for pos in sorted(portfolio["closed_positions"], key=lambda x: x["exit_datetime"]):
        cumulative += pos["realised_pnl"]
        realised_over_time.append({"date": pos["exit_datetime"], "cumulative_realised": cumulative})
    if realised_over_time:
        realised_df = pd.DataFrame(realised_over_time)
        realised_df["date"] = pd.to_datetime(realised_df["date"])
        fig = px.line(realised_df, x="date", y="cumulative_realised", title="Cumulative Realised Profit/Loss Over Time")
        st.plotly_chart(fig)
        st.write("**Realised P/L over time:** Shows total gains/losses from closed pretend trades building up.")

# Profit/Loss by Asset Class
if portfolio["closed_positions"]:
    asset_pnl = defaultdict(float)
    for pos in portfolio["closed_positions"]:
        asset_class = classify_asset_class(pos["symbol"])
        asset_pnl[asset_class] += pos["realised_pnl"]
    if asset_pnl:
        asset_df = pd.DataFrame(list(asset_pnl.items()), columns=["Asset Class", "Total P/L"])
        fig = px.bar(asset_df, x="Asset Class", y="Total P/L", title="Total Profit/Loss by Asset Class")
        st.plotly_chart(fig)
        st.write("**Profit/loss by asset class:** Bars show total pretend gains/losses for stocks, ETFs, or crypto.")

# Profit/Loss by Signal Type
if portfolio["closed_positions"]:
    signal_pnl = defaultdict(float)
    for pos in portfolio["closed_positions"]:
        signal_type = pos.get("signal_type", "unknown")
        signal_pnl[signal_type] += pos["realised_pnl"]
    if signal_pnl:
        signal_df = pd.DataFrame(list(signal_pnl.items()), columns=["Signal Type", "Total P/L"])
        fig = px.bar(signal_df, x="Signal Type", y="Total P/L", title="Total Profit/Loss by Signal Type")
        st.plotly_chart(fig)
        st.write("**Profit/loss by signal type:** Bars show total pretend gains/losses for each type of market signal.")

# Open vs Closed Trades
open_value = sum(calculate_position_metrics(pos)["current_value"] for pos in portfolio["positions"])
closed_value = sum(pos["realised_pnl"] for pos in portfolio["closed_positions"]) + starting_cash
trade_counts = {"Open Trades": open_count, "Closed Trades": closed_count}
fig = px.pie(names=list(trade_counts.keys()), values=list(trade_counts.values()), title="Open vs Closed Pretend Trades")
st.plotly_chart(fig)
st.write("**Open vs closed trades:** Pie chart shows how many pretend trades are still open versus finished.")


# Signal Type Analytics
st.subheader("Signal Type Analytics")
st.write("**What is this?** This groups your closed pretend trades by the type of market signal you used. It shows which signal types led to the best results. This helps you learn which signals to focus on for better pretend trading in the future.")
if portfolio["closed_positions"]:
    from collections import defaultdict
    signal_groups = defaultdict(list)
    for pos in portfolio["closed_positions"]:
        signal_groups[pos.get("signal_type", "unknown")].append(pos)
    
    analytics_data = []
    for signal_type, trades in signal_groups.items():
        num_trades = len(trades)
        winning = [t for t in trades if t["realised_pnl"] > 0]
        win_rate = len(winning) / num_trades * 100 if num_trades > 0 else 0
        avg_pnl = sum(t["realised_pnl"] for t in trades) / num_trades if num_trades > 0 else 0
        total_pnl = sum(t["realised_pnl"] for t in trades)
        best = max(t["realised_pnl"] for t in trades) if trades else 0
        worst = min(t["realised_pnl"] for t in trades) if trades else 0
        analytics_data.append({
            "Signal Type": signal_type,
            "Number of Trades": num_trades,
            "Win Rate %": f"{win_rate:.1f}%",
            "Average P/L": format_currency(avg_pnl),
            "Total P/L": format_currency(total_pnl),
            "Best Result": format_currency(best),
            "Worst Result": format_currency(worst),
        })
    st.dataframe(pd.DataFrame(analytics_data), use_container_width=True)
else:
    st.info("No closed pretend trades yet. Close some trades to see signal type analytics.")

# Closure Reason Analytics
st.subheader("Closure Reason Analytics")
st.write("**What is this?** This groups your closed pretend trades by why you decided to exit. Reviewing your exits is an important learning tool—it helps you understand what worked and what didn't in your pretend trading decisions.")
st.write("**Why review exits?** Knowing why you closed trades teaches you about discipline, timing, and strategy. It shows patterns in your pretend trading behavior.")
if portfolio["closed_positions"]:
    reason_groups = defaultdict(list)
    for pos in portfolio["closed_positions"]:
        reason = pos.get("closure_reason", "Not recorded")
        reason_groups[reason].append(pos)
    
    reason_data = []
    for reason, trades in reason_groups.items():
        num_trades = len(trades)
        winning = [t for t in trades if t["realised_pnl"] > 0]
        win_rate = len(winning) / num_trades * 100 if num_trades > 0 else 0
        total_pnl = sum(t["realised_pnl"] for t in trades)
        avg_pnl = total_pnl / num_trades if num_trades > 0 else 0
        best = max(t["realised_pnl"] for t in trades) if trades else 0
        worst = min(t["realised_pnl"] for t in trades) if trades else 0
        reason_data.append({
            "Closure Reason": reason,
            "Number of Trades": num_trades,
            "Win Rate %": f"{win_rate:.1f}%",
            "Average P/L": format_currency(avg_pnl),
            "Total P/L": format_currency(total_pnl),
            "Best Result": format_currency(best),
            "Worst Result": format_currency(worst),
        })
    st.dataframe(pd.DataFrame(reason_data), use_container_width=True)
else:
    st.info("No closed pretend trades yet. Close some trades to see closure reason analytics.")

# Asset Class Analytics
st.subheader("Asset Class Analytics")
st.write("**What is this?** This groups your closed pretend trades by asset class (Stocks, ETFs, Crypto). It compares how different types of investments performed in your pretend trading.")
st.write("**Important note:** Crypto is usually much more volatile than stocks or ETFs. Prices can change very quickly, so pretend trades in crypto might show bigger wins or losses.")
if portfolio["closed_positions"]:
    from collections import defaultdict
    asset_groups = defaultdict(list)
    for pos in portfolio["closed_positions"]:
        asset_class = classify_asset_class(pos["symbol"])
        asset_groups[asset_class].append(pos)
    
    asset_data = []
    for asset_class, trades in asset_groups.items():
        num_trades = len(trades)
        winning = [t for t in trades if t["realised_pnl"] > 0]
        win_rate = len(winning) / num_trades * 100 if num_trades > 0 else 0
        total_pnl = sum(t["realised_pnl"] for t in trades)
        avg_pnl = total_pnl / num_trades if num_trades > 0 else 0
        holding_times = []
        for t in trades:
            try:
                entry_dt = datetime.strptime(t["entry_datetime"], "%Y-%m-%d %H:%M:%S")
                exit_dt = datetime.strptime(t["exit_datetime"], "%Y-%m-%d %H:%M:%S")
                holding_times.append((exit_dt - entry_dt).total_seconds() / 86400)  # days
            except:
                pass
        avg_holding_days = sum(holding_times) / len(holding_times) if holding_times else 0
        best = max(t["realised_pnl"] for t in trades) if trades else 0
        worst = min(t["realised_pnl"] for t in trades) if trades else 0
        asset_data.append({
            "Asset Class": asset_class,
            "Number of Trades": num_trades,
            "Win Rate %": f"{win_rate:.1f}%",
            "Total Pretend P/L": format_currency(total_pnl),
            "Average Pretend P/L": format_currency(avg_pnl),
            "Average Holding Time (Days)": f"{avg_holding_days:.1f}",
            "Best Trade": format_currency(best),
            "Worst Trade": format_currency(worst),
        })
    st.dataframe(pd.DataFrame(asset_data), use_container_width=True)
else:
    st.info("No closed pretend trades yet. Close some trades to see asset class analytics.")


# Holding Period Analytics
st.subheader("Holding Period Analytics")
st.write("**What is this?** This groups your closed pretend trades by how long you held them. It shows if short-term or longer-term pretend trading worked better for you.")
st.write("**What this teaches:** Short-term trades (same day) can be exciting but risky. Longer-term trades (weeks) might be more stable but miss quick opportunities. This helps you learn your pretend trading style.")
if portfolio["closed_positions"]:
    def get_holding_category(days):
        if days < 1:
            return "Same Day"
        elif days <= 3:
            return "1–3 Days"
        elif days <= 7:
            return "4–7 Days"
        elif days <= 14:
            return "8–14 Days"
        else:
            return "15+ Days"
    
    holding_groups = defaultdict(list)
    for pos in portfolio["closed_positions"]:
        try:
            entry_dt = datetime.strptime(pos["entry_datetime"], "%Y-%m-%d %H:%M:%S")
            exit_dt = datetime.strptime(pos["exit_datetime"], "%Y-%m-%d %H:%M:%S")
            days = (exit_dt - entry_dt).total_seconds() / 86400
            category = get_holding_category(days)
            holding_groups[category].append(pos)
        except:
            holding_groups["Unknown"].append(pos)
    
    holding_data = []
    for period, trades in holding_groups.items():
        num_trades = len(trades)
        winning = [t for t in trades if t["realised_pnl"] > 0]
        win_rate = len(winning) / num_trades * 100 if num_trades > 0 else 0
        total_pnl = sum(t["realised_pnl"] for t in trades)
        avg_pnl = total_pnl / num_trades if num_trades > 0 else 0
        holding_data.append({
            "Holding Period": period,
            "Number of Trades": num_trades,
            "Win Rate %": f"{win_rate:.1f}%",
            "Average Profit/Loss": format_currency(avg_pnl),
            "Total Profit/Loss": format_currency(total_pnl),
        })
    # Sort by period order
    order = ["Same Day", "1–3 Days", "4–7 Days", "8–14 Days", "15+ Days", "Unknown"]
    holding_data.sort(key=lambda x: order.index(x["Holding Period"]) if x["Holding Period"] in order else len(order))
    st.dataframe(pd.DataFrame(holding_data), use_container_width=True)
else:
    st.info("No closed pretend trades yet. Close some trades to see holding period analytics.")


# Insights Summary
st.subheader("Insights Summary")
st.write("**What is this?** This is an automatic summary of patterns from your pretend trading so far. Remember, this is educational only and not financial advice. Past pretend results don't predict future real results.")

insights = []

# Asset class best
if portfolio["closed_positions"]:
    asset_totals = defaultdict(float)
    for pos in portfolio["closed_positions"]:
        asset_class = classify_asset_class(pos["symbol"])
        asset_totals[asset_class] += pos["realised_pnl"]
    if asset_totals:
        best_asset = max(asset_totals, key=asset_totals.get)
        insights.append(f"**Asset class with highest total pretend profit/loss so far:** {best_asset} (based on {len([p for p in portfolio['closed_positions'] if classify_asset_class(p['symbol']) == best_asset])} pretend trades)")
    else:
        insights.append("**Asset class performance:** Too few pretend trades to compare asset classes yet.")
else:
    insights.append("**Asset class performance:** No closed pretend trades yet.")

# Signal type best and worst
if portfolio["closed_positions"]:
    signal_totals = defaultdict(float)
    for pos in portfolio["closed_positions"]:
        signal_type = pos.get("signal_type", "unknown")
        signal_totals[signal_type] += pos["realised_pnl"]
    if len(signal_totals) >= 2:
        best_signal = max(signal_totals, key=signal_totals.get)
        worst_signal = min(signal_totals, key=signal_totals.get)
        insights.append(f"**Signal type with highest total pretend profit/loss so far:** {best_signal}")
        insights.append(f"**Signal type with lowest total pretend profit/loss so far:** {worst_signal}")
    elif len(signal_totals) == 1:
        only_signal = list(signal_totals.keys())[0]
        insights.append(f"**Signal type used so far:** {only_signal} (only one type tried yet)")
    else:
        insights.append("**Signal type performance:** No signal types recorded yet.")
else:
    insights.append("**Signal type performance:** No closed pretend trades yet.")

# Open trades overall
if portfolio["positions"]:
    total_unrealised = sum(calculate_position_metrics(pos)["unrealised_pnl"] for pos in portfolio["positions"])
    if total_unrealised > 0:
        insights.append("**Open pretend trades overall:** Currently showing unrealised gains")
    elif total_unrealised < 0:
        insights.append("**Open pretend trades overall:** Currently showing unrealised losses")
    else:
        insights.append("**Open pretend trades overall:** Currently flat")
else:
    insights.append("**Open pretend trades:** None currently open")

# Limited conclusions
closed_count = len(portfolio["closed_positions"])
if closed_count < 5:
    insights.append("**Important note:** You have very few closed pretend trades. It's too early to draw strong conclusions about patterns.")
elif closed_count < 20:
    insights.append("**Important note:** You have some pretend trades, but more experience is needed for reliable patterns.")
else:
    insights.append("**Important note:** You have enough pretend trades to start seeing some patterns, but remember this is practice only.")

for insight in insights:
    st.write(insight)


# Start a scan
st.subheader("Start a New Scan")
st.write("**What does this do?** Clicking 'Scan Markets' generates an updated set of pretend signals for the symbols in your watchlist. It uses paper trading mode only.")
st.write("**Scan data note:** Signals are generated from your current watchlist and built-in pretend market data. This is for learning only; no broker is connected.")
if st.button("🔍 Scan Markets", type="primary", use_container_width=True):
    st.info("Scanning the current watchlist in paper trading mode")
    st.session_state.signals, st.session_state.history, st.session_state.performance = run_scan(st.session_state.watchlist, st.session_state.history)
 
    st.session_state.last_scan_time = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S")
    st.rerun()

with st.expander("⚙️ Advanced / Reset Options"):
    st.write("Need to start again?")
    st.write("Choose which part of the demo you would like to reset.")

    st.markdown("---")
    st.subheader("Safe Resets")
    st.write("The information removed here can be recreated at any time")

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("Reset Watchlist."):
            default_watchlist = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "BTC-USD", "ETH-USD"]
            st.session_state.watchlist = default_watchlist
            st.session_state.watchlist_edit = ", ".join(default_watchlist)
            watchlist = st.session_state.watchlist
            st.success("Watchlist has been reset to beginner defaults.")

    with col2:
        st.write("Returns the watchlist to the default assets")

    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("Clear scan results"):
            st.session_state.signals = []
            st.session_state.history = []
            st.session_state.performance = {"total_signals": 0, "win_rate": 0.0, "total_return": 0.0}
            signals = []
            history = []
            performance = st.session_state.performance
            st.success("Scan results are cleared for this session.")
    
    with col2:
        st.write("Removes the previous scan results")

    st.markdown("---")
    st.subheader("⚠️ Permanent Data Removal")
    st.write("The information removed here cannot be recreated automatically.")
   
    
    col1, col2 = st.columns([1, 3])
    with col2:    
        st.write("Removes all pretend trades and starts again")
    clear_portfolio_confirm = st.checkbox("I understand this will clear the paper portfolio", key="confirm_clear_portfolio")

    with col1:
        if st.button("Clear paper portfolio"):
            if clear_portfolio_confirm:
                st.session_state.portfolio = default_portfolio()
                save_portfolio(st.session_state.portfolio)
                portfolio = st.session_state.portfolio
                st.success("Paper portfolio has been cleared.")
            else:
                st.warning("Please confirm before clearing the paper portfolio.")
    

    
    col1, col2 = st.columns([1, 3])
    with col2:
        st.write("Clears all tester feedback")
    clear_feedback_confirm = st.checkbox("I understand this will clear saved tester feedback", key="confirm_clear_feedback")
    
    with col1:
        if st.button("Clear tester feedback"):
            if clear_feedback_confirm:
                if os.path.exists("tester_feedback.csv"):
                    os.remove("tester_feedback.csv")
                st.success("Tester feedback has been cleared.")
            else:
                st.warning("Please confirm before clearing tester feedback.")
    

# Tester Feedback
st.subheader("Tester Feedback")
st.write("Please share what was easy to use, confusing, or missing. This helps improve the demo quickly.")
confused = st.text_area("What confused you?", "")
liked = st.text_area("What did you like?", "")
expected = st.text_area("What did you expect to happen?", "")
broke = st.selectbox("Did anything break?", ["No", "Yes, it had a problem", "Not sure"])
other_comments = st.text_area("Any other comments?", "")
if st.button("Submit tester feedback"):
    feedback_entry = {
        "timestamp": datetime.now().isoformat(),
        "confused": confused,
        "liked": liked,
        "expected": expected,
        "broke": broke,
        "other_comments": other_comments
    }
    save_tester_feedback(feedback_entry)
    st.success("Thank you! Your feedback was saved locally in tester_feedback.csv.")

# Data Storage
st.subheader("Data Storage")
st.write("**How is data stored?** Signals and history are saved in simple files on your computer for demo purposes. In a real app, they'd be in a secure database. Watchlist and trades are temporary and reset when you close the app.")
st.write("Signals and history are stored locally in JSON files for demonstration. In production, use a database like SQLite or PostgreSQL.")
st.write("Watchlist and trades are stored in session state (temporary).")

# Learning Journal
st.subheader("Learning Journal")
st.write("**What is this?** This is your personal notes section. For each signal, write what you think it means, if you understood it, and what happened later (e.g., did the stock go up?). Your notes are saved locally on your computer.")
all_signals = [s["symbol"] for s in signals + history]
if all_signals:
    selected_signal = st.selectbox("Choose a signal to journal about", all_signals, key="journal_select")

    if selected_signal:
        st.write(f"**Journal for {selected_signal}:**")
        what_it_means = st.text_area("What do you think this signal means?", value=journal.get(selected_signal, {}).get("what_it_means", ""), key=f"means_{selected_signal}")
        understood = st.radio("Did you understand this signal?", ["Yes", "No", "Somewhat"], index=["Yes", "No", "Somewhat"].index(journal.get(selected_signal, {}).get("understood", "Somewhat")), key=f"understood_{selected_signal}")
        what_happened = st.text_area("What happened later? (e.g., stock price changes)", value=journal.get(selected_signal, {}).get("what_happened", ""), key=f"happened_{selected_signal}")
        
        if st.button("Save Notes", key=f"save_{selected_signal}"):
            journal[selected_signal] = {
                "what_it_means": what_it_means,
                "understood": understood,
                "what_happened": what_happened
            }
            save_journal(journal)
            st.success("Notes saved!")
else:
    st.info("No signals are available yet to journal about. Run a scan to generate signal data.")

# Glossary
st.subheader("Glossary: Key Terms Explained")
st.markdown("""
- **Signal:** A recommendation to buy, sell, or hold a stock based on analysis.
- **Confidence Score:** A number (0-100) showing how sure the system is about the signal. Higher is better.
- **Traffic Light Labels:** Color-coded guides like traffic lights: 🔴 High caution (be careful), 🟢 Strong movement (good to act), 🟡 Worth studying (learn more), 🔵 Low interest (low priority).
- **Symbol/Ticker:** A short code for a stock, like 'AAPL' for Apple.
- **Volume:** The number of shares traded. High volume means lots of interest.
- **RSI (Relative Strength Index):** A measure of whether a stock is overbought (too high) or oversold (too low). Above 70 is overbought, below 30 is oversold.
- **MACD (Moving Average Convergence Divergence):** A tool to spot changes in momentum. Bullish means upward trend, bearish means downward.
- **Win Rate:** The percentage of signals that led to profits.
- **Total Return:** The overall gain or loss from following signals.
- **Paper Trading:** Pretend trading with no real money to practice.
- **Watchlist:** A personal list of stocks you want to track.
- **Scan:** Checking the market for new signals.
""")
