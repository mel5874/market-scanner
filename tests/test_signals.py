from pathlib import Path

import pandas as pd

from market_scanner.backtesting import summarize_backtest
from market_scanner.config import Settings
from market_scanner.paper_trading import PaperPortfolio
from market_scanner.scoring import rank_signals
from market_scanner.safety import assert_paper_trading_only
from market_scanner.signals import detect_signal
from market_scanner.storage import SignalStore


def sample_frame(rows: int = 35) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = [100 + i * 0.2 for i in range(rows)]
    high = [price + 1 for price in close]
    low = [price - 1 for price in close]
    volume = [1000 for _ in range(rows)]
    # Force breakout, big move, unusual volume, and volatility spike on final bar.
    close[-1] = 115
    high[-1] = 118
    low[-1] = 108
    volume[-1] = 5000
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


def test_detect_signal_identifies_breakout_and_volume() -> None:
    settings = Settings(database_path=Path(":memory:"))
    signal = detect_signal("TEST", sample_frame(), settings)

    assert signal is not None
    assert signal.symbol == "TEST"
    assert signal.is_breakout
    assert signal.is_unusual_volume
    assert signal.is_big_mover
    assert "unusual volume" in "; ".join(signal.reasons)


def test_rank_signals_adds_trade_idea_and_score() -> None:
    settings = Settings(database_path=Path(":memory:"))
    signal = detect_signal("TEST", sample_frame(), settings)
    ranked = rank_signals([signal])  # type: ignore[list-item]

    assert ranked[0].score > 0
    assert 0 <= ranked[0].confidence <= 1
    assert "Paper entry zone" in ranked[0].trade_idea
    assert ranked[0].risk_reward >= 0


def test_signal_store_writes_sqlite_and_csv(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "signals.sqlite", csv_log_path=tmp_path / "signals.csv")
    signal = rank_signals([detect_signal("TEST", sample_frame(), settings)])[0]  # type: ignore[list-item]
    store = SignalStore(settings.database_path, settings.csv_log_path)

    store.save_signals([signal])
    recent = store.load_recent(limit=1)

    assert recent[0]["symbol"] == "TEST"
    assert settings.csv_log_path.exists()


def test_summarize_backtest_empty() -> None:
    assert summarize_backtest(pd.DataFrame())["trades"] == 0


def test_safety_guard_rejects_live_trading_flag(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")

    try:
        assert_paper_trading_only("paper")
    except RuntimeError as exc:
        assert "Live-trading" in str(exc)
    else:  # pragma: no cover - explicit failure path for readability
        raise AssertionError("live trading flag should fail startup")


def test_paper_proposal_respects_risk_caps() -> None:
    settings = Settings(
        database_path=Path(":memory:"),
        paper_starting_cash=10_000,
        max_position_pct=0.50,
        max_trade_risk_pct=0.01,
        max_trade_risk_dollars=75,
        max_daily_paper_risk_pct=0.03,
    )
    signal = rank_signals([detect_signal("TEST", sample_frame(), settings)])[0]  # type: ignore[list-item]
    portfolio = PaperPortfolio.from_settings(settings)

    proposal = portfolio.propose_order(signal)

    assert proposal.mode == "paper-only"
    assert proposal.dollars_at_risk <= 75
    assert proposal.allocation <= 5_000
