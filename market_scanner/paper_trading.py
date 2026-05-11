"""Paper-trading simulator. No live orders are placed by this module."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Settings
from .safety import assert_paper_trading_only
from .signals import Signal


@dataclass
class PaperPosition:
    symbol: str
    quantity: float
    entry_price: float
    stop_loss: float
    target: float
    signal_score: int
    dollars_at_risk: float


@dataclass
class PaperOrderProposal:
    """Display-only paper order idea; it is never sent to a broker."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    allocation: float
    stop_loss: float
    target: float
    dollars_at_risk: float
    max_allowed_risk: float
    mode: str = "paper-only"
    warning: str = "Simulation only. No real order is placed."

    def as_dict(self) -> dict[str, float | str]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "allocation": self.allocation,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "dollars_at_risk": self.dollars_at_risk,
            "max_allowed_risk": self.max_allowed_risk,
            "mode": self.mode,
            "warning": self.warning,
        }


@dataclass
class PaperPortfolio:
    """Simple in-memory paper portfolio for educational position sizing."""

    starting_cash: float = 25_000.0
    max_position_pct: float = 0.10
    max_trade_risk_pct: float = 0.01
    max_trade_risk_dollars: float = 250.0
    max_daily_paper_risk_pct: float = 0.03
    max_open_paper_positions: int = 5
    trading_mode: str = "paper"
    cash: float = field(init=False)
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    daily_risk_used: float = 0.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "PaperPortfolio":
        return cls(
            starting_cash=settings.paper_starting_cash,
            max_position_pct=settings.max_position_pct,
            max_trade_risk_pct=settings.max_trade_risk_pct,
            max_trade_risk_dollars=settings.max_trade_risk_dollars,
            max_daily_paper_risk_pct=settings.max_daily_paper_risk_pct,
            max_open_paper_positions=settings.max_open_paper_positions,
            trading_mode=settings.trading_mode,
        )

    def __post_init__(self) -> None:
        assert_paper_trading_only(self.trading_mode)
        if self.starting_cash <= 0:
            raise ValueError("PAPER_STARTING_CASH must be greater than zero")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("MAX_POSITION_PCT must be between 0 and 1")
        if not 0 < self.max_trade_risk_pct <= 1:
            raise ValueError("MAX_TRADE_RISK_PCT must be between 0 and 1")
        if self.max_trade_risk_dollars <= 0:
            raise ValueError("MAX_TRADE_RISK_DOLLARS must be greater than zero")
        if not 0 < self.max_daily_paper_risk_pct <= 1:
            raise ValueError("MAX_DAILY_PAPER_RISK_PCT must be between 0 and 1")
        if self.max_open_paper_positions < 1:
            raise ValueError("MAX_OPEN_PAPER_POSITIONS must be at least 1")
        self.cash = self.starting_cash

    @property
    def max_daily_paper_risk_dollars(self) -> float:
        return self.starting_cash * self.max_daily_paper_risk_pct

    @property
    def per_trade_risk_limit(self) -> float:
        pct_limit = self.starting_cash * self.max_trade_risk_pct
        return min(pct_limit, self.max_trade_risk_dollars)

    def propose_order(self, signal: Signal) -> PaperOrderProposal:
        """Return a paper order proposal without executing against a broker."""

        assert_paper_trading_only(self.trading_mode)
        if len(self.positions) >= self.max_open_paper_positions:
            raise ValueError("Maximum open paper positions reached")

        entry = signal.entry_zone_high or signal.close
        stop = signal.stop_loss
        risk_per_share = max(entry - stop, 0.01)
        remaining_daily_risk = max(self.max_daily_paper_risk_dollars - self.daily_risk_used, 0.0)
        max_allowed_risk = min(self.per_trade_risk_limit, remaining_daily_risk)
        max_allocation = min(self.cash, self.starting_cash * self.max_position_pct)
        risk_based_quantity = max_allowed_risk / risk_per_share if risk_per_share else 0.0
        allocation_based_quantity = max_allocation / entry if entry else 0.0
        quantity = max(0.0, min(risk_based_quantity, allocation_based_quantity))
        allocation = quantity * entry
        dollars_at_risk = quantity * risk_per_share

        return PaperOrderProposal(
            symbol=signal.symbol,
            side="BUY-WATCH",
            quantity=round(quantity, 6),
            entry_price=round(entry, 4),
            allocation=round(allocation, 2),
            stop_loss=signal.stop_loss,
            target=signal.target,
            dollars_at_risk=round(dollars_at_risk, 2),
            max_allowed_risk=round(max_allowed_risk, 2),
        )

    def open_paper_position(self, signal: Signal) -> PaperPosition | None:
        """Open a simulated paper position from a signal; never contacts a broker."""

        proposal = self.propose_order(signal)
        allocation = proposal.allocation
        quantity = proposal.quantity
        if allocation <= 0 or quantity <= 0 or signal.symbol in self.positions:
            return None

        self.cash -= allocation
        self.daily_risk_used += proposal.dollars_at_risk
        position = PaperPosition(
            symbol=signal.symbol,
            quantity=quantity,
            entry_price=proposal.entry_price,
            stop_loss=signal.stop_loss,
            target=signal.target,
            signal_score=signal.score,
            dollars_at_risk=proposal.dollars_at_risk,
        )
        self.positions[signal.symbol] = position
        return position
