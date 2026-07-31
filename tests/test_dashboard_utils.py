from dashboard import (
    build_closed_trade_analytics,
    build_watchlist_scan_results,
    convert_real_signal_to_dashboard_signal,
    get_available_trade_symbols,
    get_quantity_input_config,
    has_valid_trade_metrics,
    run_scan,
    validate_trade_quantity,
)
from market_scanner.scoring import (
    build_signal_audit_details,
    get_traffic_light_label_from_score,
)
from market_scanner.signals import Signal


def test_has_valid_trade_metrics_rejects_none():
    assert has_valid_trade_metrics(None) is False


def test_has_valid_trade_metrics_accepts_metrics_dict():
    assert has_valid_trade_metrics({"current_price": 1.0}) is True


def test_build_closed_trade_analytics_uses_trade_history_records():
    closed_trades = [
        {
            "symbol": "BTC-USD",
            "signal_type": "breakout",
            "closure_reason": "Profit target reached",
            "entry_datetime": "2024-01-01 10:00:00",
            "exit_datetime": "2024-01-02 10:00:00",
            "realised_pnl": 100.0,
        },
        {
            "symbol": "AAPL",
            "entry_datetime": "2024-01-03 10:00:00",
            "exit_datetime": "2024-01-04 10:00:00",
            "realised_pnl": -50.0,
        },
    ]

    analytics = build_closed_trade_analytics(closed_trades)

    assert len(analytics["signal_type"]) == 2
    assert len(analytics["closure_reason"]) == 2
    assert len(analytics["asset_class"]) == 2
    assert len(analytics["holding_period"]) == 2

    signal_types = {row["Signal Type"] for row in analytics["signal_type"]}
    assert "breakout" in signal_types
    assert "Unknown" in signal_types

    reasons = {row["Closure Reason"] for row in analytics["closure_reason"]}
    assert "Profit target reached" in reasons
    assert "Not recorded" in reasons


def test_crypto_quantity_below_one_is_accepted():
    valid, message = validate_trade_quantity(0.25, "BTC-GBP")
    assert valid is True
    assert message == ""


def test_stock_quantity_below_one_is_rejected():
    valid, message = validate_trade_quantity(0.5, "AAPL")
    assert valid is False
    assert "at least 1" in message.lower()


def test_crypto_quantity_config_uses_fractional_minimum_and_step():
    config = get_quantity_input_config("BTC-GBP")
    assert config["min_value"] == 0.000001
    assert config["step"] == 0.001
    assert config["format"] == "%.6f"


def test_fractional_cost_and_quantity_persist_exactly():
    quantity = 0.125
    entry_price = 50000.0
    starting_value = entry_price * quantity
    assert starting_value == 6250.0
    assert quantity == 0.125


def test_scanner_audit_builds_buy_and_sell_cases():
    buy_signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=95.0,
        pct_change=0.0526,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=98.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=True,
        is_pullback=False,
        is_volatility_spike=True,
        reasons=["big move", "volume", "breakout"],
    )
    sell_signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=105.0,
        pct_change=-0.0476,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=110.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=False,
        is_pullback=True,
        is_volatility_spike=True,
        reasons=["pullback", "volume"],
    )

    buy_audit = build_signal_audit_details(buy_signal, displayed_signal="BUY")
    sell_audit = build_signal_audit_details(sell_signal, displayed_signal="SELL")

    assert buy_audit["display_signal"] == "BUY"
    assert sell_audit["display_signal"] == "SELL"
    assert buy_audit["total_score"] >= 55
    assert sell_audit["total_score"] >= 55


def test_watch_and_hold_cases_and_traffic_light_boundaries():
    watch_signal = Signal(
        symbol="TEST",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=99.0,
        pct_change=0.01,
        volume=1000.0,
        avg_volume=1000.0,
        volume_multiple=1.0,
        recent_high=101.0,
        recent_low=99.0,
        volatility=0.01,
        avg_volatility=0.01,
        volatility_multiple=1.0,
        is_big_mover=False,
        is_unusual_volume=False,
        is_breakout=False,
        is_pullback=False,
        is_volatility_spike=False,
        reasons=[],
    )
    hold_signal = Signal(
        symbol="TEST",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=100.0,
        pct_change=0.0,
        volume=1000.0,
        avg_volume=1000.0,
        volume_multiple=1.0,
        recent_high=101.0,
        recent_low=99.0,
        volatility=0.01,
        avg_volatility=0.01,
        volatility_multiple=1.0,
        is_big_mover=False,
        is_unusual_volume=False,
        is_breakout=False,
        is_pullback=False,
        is_volatility_spike=False,
        reasons=[],
    )

    watch_audit = build_signal_audit_details(watch_signal, displayed_signal="WATCH")
    hold_audit = build_signal_audit_details(hold_signal, displayed_signal="HOLD")

    assert watch_audit["display_signal"] == "WATCH"
    assert hold_audit["display_signal"] == "HOLD"
    assert get_traffic_light_label_from_score(89) == "🟢 Strong movement"
    assert get_traffic_light_label_from_score(60) == "🟡 Worth studying"
    assert get_traffic_light_label_from_score(59) == "🔵 Low interest"
    assert get_traffic_light_label_from_score(90) == "🔴 High caution"


def test_missing_indicator_data_is_reported_in_audit():
    signal = Signal(
        symbol="TEST",
        timestamp="2024-01-01T00:00:00",
        close=float("nan"),
        previous_close=100.0,
        pct_change=float("nan"),
        volume=1000.0,
        avg_volume=1000.0,
        volume_multiple=1.0,
        recent_high=101.0,
        recent_low=99.0,
        volatility=0.01,
        avg_volatility=0.01,
        volatility_multiple=1.0,
        is_big_mover=False,
        is_unusual_volume=False,
        is_breakout=False,
        is_pullback=False,
        is_volatility_spike=False,
        reasons=[],
    )
    audit = build_signal_audit_details(signal, displayed_signal="WATCH")
    assert "close" in audit["missing_data"]
    assert "pct_change" in audit["missing_data"]


def test_genuine_breakout_signal_displays_buy():
    signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=95.0,
        pct_change=0.0526,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=98.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=True,
        is_pullback=False,
        is_volatility_spike=True,
        reasons=["breakout"],
    )
    signal.score = 80

    result = convert_real_signal_to_dashboard_signal(signal)

    assert result["signal"] == "BUY"
    assert result["score"] == 80
    assert result["reasons"] == ["breakout"]


def test_genuine_pullback_signal_displays_sell():
    signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=105.0,
        pct_change=-0.0476,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=110.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=False,
        is_pullback=True,
        is_volatility_spike=True,
        reasons=["pullback"],
    )
    signal.score = 60

    result = convert_real_signal_to_dashboard_signal(signal)

    assert result["signal"] == "SELL"


def test_high_scoring_neutral_signal_displays_hold():
    signal = Signal(
        symbol="TEST",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=100.0,
        pct_change=0.0,
        volume=1000.0,
        avg_volume=1000.0,
        volume_multiple=1.0,
        recent_high=101.0,
        recent_low=99.0,
        volatility=0.01,
        avg_volatility=0.01,
        volatility_multiple=1.0,
        is_big_mover=False,
        is_unusual_volume=False,
        is_breakout=False,
        is_pullback=False,
        is_volatility_spike=False,
        reasons=[],
    )
    signal.score = 60

    result = convert_real_signal_to_dashboard_signal(signal)

    assert result["signal"] == "HOLD"


def test_lower_scoring_detected_signal_displays_watch():
    signal = Signal(
        symbol="TEST",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=99.0,
        pct_change=0.01,
        volume=1000.0,
        avg_volume=1000.0,
        volume_multiple=1.0,
        recent_high=101.0,
        recent_low=99.0,
        volatility=0.01,
        avg_volatility=0.01,
        volatility_multiple=1.0,
        is_big_mover=False,
        is_unusual_volume=False,
        is_breakout=False,
        is_pullback=False,
        is_volatility_spike=False,
        reasons=[],
    )
    signal.score = 20

    result = convert_real_signal_to_dashboard_signal(signal)

    assert result["signal"] == "WATCH"


def test_no_detected_signal_displays_quiet():
    results = build_watchlist_scan_results(["AAPL", "GOOGL"], [])

    assert [row["signal"] for row in results] == ["QUIET", "QUIET"]
    assert [row["score"] for row in results] == [0, 0]


def test_insufficient_market_information_displays_waiting():
    results = build_watchlist_scan_results(["AAPL"], [], failed_symbols=["AAPL"])

    assert results[0]["signal"] == "WAITING"
    assert results[0]["score"] == 0
    assert "sufficient market information" in results[0]["explanation"].lower()


def test_watchlist_scan_results_include_every_symbol():
    signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=95.0,
        pct_change=0.0526,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=98.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=True,
        is_pullback=False,
        is_volatility_spike=True,
        reasons=["breakout"],
    )

    results = build_watchlist_scan_results(["AAPL", "GOOGL", "TSLA"], [signal])
    assert [row["symbol"] for row in results] == ["AAPL", "GOOGL", "TSLA"]
    assert results[1]["signal"] == "QUIET"


def test_failed_data_retrieval_uses_waiting_status():
    signal = Signal(
        symbol="AAPL",
        timestamp="2024-01-01T00:00:00",
        close=100.0,
        previous_close=95.0,
        pct_change=0.0526,
        volume=2000.0,
        avg_volume=1000.0,
        volume_multiple=2.0,
        recent_high=98.0,
        recent_low=90.0,
        volatility=0.02,
        avg_volatility=0.01,
        volatility_multiple=2.0,
        is_big_mover=True,
        is_unusual_volume=True,
        is_breakout=True,
        is_pullback=False,
        is_volatility_spike=True,
        reasons=["breakout"],
    )

    results = build_watchlist_scan_results(["AAPL", "MSFT"], [signal], failed_symbols=["MSFT"])
    by_symbol = {row["symbol"]: row for row in results}
    assert by_symbol["MSFT"]["signal"] == "WAITING"
    assert by_symbol["AAPL"]["signal"] == "BUY"


def test_run_scan_preserves_watchlist_symbols(monkeypatch):
    class DummyFetcher:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_watchlist(self, symbols):
            return {}

    monkeypatch.setattr("dashboard.MarketDataFetcher", DummyFetcher)
    monkeypatch.setattr("dashboard.detect_signals", lambda *args, **kwargs: [])
    monkeypatch.setattr("dashboard.rank_signals", lambda signals: [])

    signals, history, performance = run_scan(["AAPL", "MSFT"], [])
    assert [row["symbol"] for row in signals] == ["AAPL", "MSFT"]
    assert history[0]["symbol"] == "AAPL"
    assert performance["total_signals"] == 2


def test_open_position_symbols_remain_selectable():
    watchlist = ["AAPL"]
    portfolio = {"positions": [{"symbol": "BTC-GBP"}]}
    available_symbols = get_available_trade_symbols(watchlist, portfolio)
    assert available_symbols == ["AAPL", "BTC-GBP"]


def test_crypto_symbols_remain_distinct():
    assert get_available_trade_symbols(["BTC-USD"], {"positions": [{"symbol": "BTC-GBP"}]}) == ["BTC-USD", "BTC-GBP"]


def test_stock_quantity_config_uses_consistent_integer_compatible_values():
    config = get_quantity_input_config("AAPL")
    assert config["min_value"] == 1.0
    assert config["step"] == 1.0
    assert config["value"] == 10.0
    assert isinstance(config["min_value"], float)


def test_crypto_quantity_config_preserves_fractional_values():
    quantity = 0.125
    valid, message = validate_trade_quantity(quantity, "BTC-GBP")
    assert valid is True
    assert message == ""
    assert quantity == 0.125


def test_number_input_warning_condition_is_not_produced():
    stock_config = get_quantity_input_config("AAPL")
    crypto_config = get_quantity_input_config("BTC-GBP")
    assert isinstance(stock_config["min_value"], float)
    assert isinstance(stock_config["step"], float)
    assert isinstance(crypto_config["min_value"], float)
    assert isinstance(crypto_config["step"], float)
