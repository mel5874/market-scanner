import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os
import csv

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
        "positions": [],
        "closed_positions": [],
        "trade_history": [],
        "balance_history": [{"date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "balance": 10000.0}],
    }


def load_portfolio():
    try:
        if os.path.exists("portfolio.json"):
            with open("portfolio.json", "r") as f:
                return json.load(f)
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
    prices = {
        "AAPL": 170.50,
        "GOOGL": 2850.75,
        "TSLA": 980.20,
        "MSFT": 335.60,
        "AMZN": 142.30,
        "SPY": 445.10,
        "QQQ": 360.80,
        "BTC-USD": 67000.00,
        "ETH-USD": 3300.00,
        "XRP": 0.54,
        "SOL-USD": 120.00,
        "NVDA": 460.30,
        "ADA": 0.40,
        "VTI": 210.15,
        "IWM": 214.30,
    }
    return prices.get(symbol, 100.0)


def get_default_watchlist():
    return ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]


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

    buy_signals = sum(1 for s in history if s.get("signal") == "BUY")
    win_rate = buy_signals / total_signals * 100
    return {"total_signals": total_signals, "win_rate": win_rate, "total_return": 0.0}


def run_scan(watchlist, history):
    valid_watchlist = [s.strip().upper() for s in (watchlist or []) if isinstance(s, str) and s.strip()]
    new_signals = [generate_signal_for_symbol(symbol) for symbol in valid_watchlist]
    new_history = history + new_signals
    performance = calculate_performance_metrics(new_history)
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
st.title("Market Scanner Dashboard")

st.error("""
⚠️ TESTER / DEMO MODE

- Educational and research purposes only
- Not financial advice
- Paper trading only
- Signals may be inaccurate
- Do not use this for live trading decisions
""")

st.info("This is an early demo version for learning. Scan results are generated from the current watchlist and pretend market data only. No broker is connected and no live trading is included.")

st.subheader("How to start")
st.write("1. Add symbols to the Watchlist section below so the dashboard knows what to follow.")
st.write("2. Click 'Scan Markets' to update the latest signals and refresh the tables on this page.")
st.write("3. Use 'Explain This Signal' to learn why a signal appeared and what risks to watch.")
st.write("4. Review the warning messages before entering any pretend trades.")
st.write("5. Use the Paper Trading section to simulate a trade with pretend money.")
st.write("6. Check Open Pretend Trades, Closed Pretend Trades, and Performance Analytics to learn from the results.")

st.subheader("Reset / Demo Controls")
st.write("Use these buttons to keep the demo safe and easy to restart.")
if st.button("Reset watchlist to beginner defaults"):
    default_watchlist = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN", "BTC-USD", "ETH-USD"]
    st.session_state.watchlist = default_watchlist
    st.session_state.watchlist_edit = ", ".join(default_watchlist)
    watchlist = st.session_state.watchlist
    st.success("Watchlist has been reset to beginner defaults.")

if st.button("Clear scan results"):
    st.session_state.signals = []
    st.session_state.history = []
    st.session_state.performance = {"total_signals": 0, "win_rate": 0.0, "total_return": 0.0}
    signals = []
    history = []
    performance = st.session_state.performance
    st.success("Scan results are cleared for this session.")

clear_portfolio_confirm = st.checkbox("I understand this will clear the paper portfolio", key="confirm_clear_portfolio")
if st.button("Clear paper portfolio"):
    if clear_portfolio_confirm:
        st.session_state.portfolio = default_portfolio()
        save_portfolio(st.session_state.portfolio)
        portfolio = st.session_state.portfolio
        st.success("Paper portfolio has been cleared.")
    else:
        st.warning("Please confirm before clearing the paper portfolio.")

clear_feedback_confirm = st.checkbox("I understand this will clear saved tester feedback", key="confirm_clear_feedback")
if st.button("Clear tester feedback"):
    if clear_feedback_confirm:
        if os.path.exists("tester_feedback.csv"):
            os.remove("tester_feedback.csv")
        st.success("Tester feedback has been cleared.")
    else:
        st.warning("Please confirm before clearing tester feedback.")

# App title
st.markdown("**Welcome!** This dashboard helps beginners like you understand market signals. It shows buy/sell/hold recommendations for stocks based on data analysis. Everything is explained in simple terms below.")

# Disclaimer reminder
st.warning("This tool is educational only, paper trading only, and does not connect to a broker. Always do your own research before using real money.")

# Latest scan timestamp
if st.session_state.last_scan_time:
    st.subheader(f"Latest Scan: {st.session_state.last_scan_time}")
    st.write("**What is this?** This is the date and time when you last clicked 'Scan Markets'. It tells you how fresh the signals are. If it's old, the market may have changed since then.")
else:
    st.subheader("Latest Scan: No scans run yet")
    st.info("Click 'Scan Markets' below to see the latest market signals and update this timestamp.")

# Performance summary cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Signals", performance["total_signals"])
    st.write("**Total Signals:** The number of buy/sell/hold recommendations generated so far. More signals mean more analysis done.")
with col2:
    st.metric("Win Rate (%)", f"{performance['win_rate']:.1f}")
    st.write("**Win Rate:** A simple percent metric based on how many buy signals exist compared with total signals in this session.")
with col3:
    st.metric("Total Return (%)", f"{performance['total_return']:.1f}")
    st.write("**Total Return:** A placeholder value in this paper trading demo until more pretend trading history is available.")

# Charts for signals
st.subheader("Signal Distribution")
st.write("**What is this chart?** This bar chart shows how many buy, sell, or hold signals were found in the latest scan of your current watchlist.")
if signals:
    signal_counts = pd.DataFrame(signals).groupby("signal").size().reset_index(name="count")
    fig = px.bar(signal_counts, x="signal", y="count", title="Signals by Type")
    st.plotly_chart(fig)
else:
    st.warning("Not enough fresh scan data yet — run more scans to build this view.")

# Confidence scores chart
st.subheader("Confidence Scores")
st.write("**What is this chart?** This scatter plot shows each stock's signal confidence from the latest scan. Bigger dots mean higher confidence.")
if signals:
    fig2 = px.scatter(pd.DataFrame(signals), x="symbol", y="confidence", color="signal", size="confidence", title="Signal Confidence")
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

# Explain This Signal
st.subheader("Explain This Signal")
st.write("**What is this?** Select a signal to get a simple explanation of why it appeared, what could go wrong, and what to check before trying a paper trade. This helps beginners understand risks and do their homework.")
all_signals_for_explain = signals + history
if all_signals_for_explain:
    signal_options = [f"{s['symbol']} ({s['signal']})" for s in all_signals_for_explain]
    selected_explain = st.selectbox("Choose a signal to explain", signal_options, key="explain_select")

    if selected_explain:
        selected_data = next(s for s in all_signals_for_explain if f"{s['symbol']} ({s['signal']})" == selected_explain)
        st.write(f"**Why did the {selected_data['signal']} signal for {selected_data['symbol']} appear?** {selected_data['why_appeared']}")
        st.write(f"**What could go wrong?** {selected_data['what_could_go_wrong']}")
        st.write(f"**What should I check before a paper trade?** {selected_data['what_to_check']}")
else:
    st.info("No signals are available yet. Run a scan to generate signal explanations.")

# Signal history table
st.subheader("Signal History")
st.write("**What is this table?** This is a list of all past signals, including older ones. It helps you see patterns over time. Same columns as above.")
history_df = pd.DataFrame(history)
st.dataframe(history_df)

# Watchlist management
st.subheader("Watchlist")
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
        portfolio["positions"].append(new_position)
        save_portfolio(portfolio)
        st.success(f"Simulated {trade_action} of {trade_quantity} shares of {trade_symbol} at {format_currency(entry_price)} based on {trade_signal_type} signal")
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
            st.write(f"Unrealised P/L: {format_currency(metrics['unrealised_pnl'])} ({format_percentage(metrics['unrealised_pct'])})")
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
total_value = starting_cash + unrealised_pnl + realised_pnl
total_return_pct = ((total_value - starting_cash) / starting_cash * 100) if starting_cash else 0.0

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

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Starting Pretend Balance", format_currency(starting_cash))
    st.write("**Starting pretend balance:** The fake money you began with (£10,000).")
    st.metric("Current Pretend Portfolio Value", format_currency(total_value))
    st.write("**Current pretend portfolio value:** Your total fake money now, including open trades.")
    st.metric("Total Pretend Profit/Loss", format_currency(total_value - starting_cash))
    st.write("**Total pretend profit/loss:** How much your fake money has changed overall.")
with col2:
    st.metric("Total Return %", format_percentage(total_return_pct))
    st.write("**Total return %:** The percentage change in your fake money.")
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
    st.write("**Win rate:** Percentage of closed trades that made money.")
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
if st.button("Scan Markets"):
    st.info("Scanning the current watchlist in paper trading mode")
    st.session_state.signals, st.session_state.history, st.session_state.performance = run_scan(st.session_state.watchlist, st.session_state.history)
    st.session_state.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success(f"Scan completed! Latest scan time: {st.session_state.last_scan_time}")
    st.rerun()

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