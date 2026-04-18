"""
Abstract base class for all trading strategies.

Strategies must not call broker APIs; execution and sizing are orchestrated
elsewhere. Risk percentage defaults come from ``CONFIG.risk``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Union

import pandas as pd

from forex_bot.config import CONFIG, AppConfig, Timeframe


class Signal(str, Enum):
    """Discrete trading signal."""

    BUY = "BUY"
    SELL = "SELL"
    FLAT = "FLAT"


@dataclass
class StrategyContext:
    """
    Market and account state passed into strategy methods.

    All timestamps in ``df`` must be UTC. Optional frames support pairs trading
    and multi-leg logic without broker calls.
    """

    instrument: str
    timeframe: Timeframe
    df: pd.DataFrame
    account_equity: float
    spread: float
    pip_size: float
    bid: float | None = None
    ask: float | None = None
    avg_spread: float | None = None
    auxiliary_frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    events_df: pd.DataFrame | None = None


TakeProfitType = Union[float, list[float]]


class BaseStrategy(ABC):
    """
    Strategy interface: signal, protective levels, sizing, and gating checks.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy identifier."""

    @abstractmethod
    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """
        Produce a directional signal and confidence in ``[0, 1]``.

        Args:
            ctx: Current market/account context.

        Returns:
            Tuple ``(signal, confidence)``.
        """

    @abstractmethod
    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """
        Stop-loss price for the given entry and direction.

        Args:
            ctx: Context (series may include ATR and structure).
            entry: Intended entry price.
            signal: Non-flat signal direction.

        Returns:
            Stop price in quote currency.
        """

    def get_take_profit(
        self,
        ctx: StrategyContext,
        entry: float,
        signal: Signal,
    ) -> TakeProfitType:
        """
        Take-profit price(s). Default: R-multiples from ``CONFIG.stops_tp``.

        Args:
            ctx: Context.
            entry: Entry price.
            signal: Direction.

        Returns:
            Single TP or a list of partial TP levels.
        """

        if signal == Signal.FLAT:
            return entry
        sl = self.get_stop_loss(ctx, entry, signal)
        r = abs(entry - sl)
        if r <= 0:
            return entry
        cfg = CONFIG.stops_tp
        tp1 = entry + cfg.tp1_r_multiple * r if signal == Signal.BUY else entry - cfg.tp1_r_multiple * r
        tp2 = entry + cfg.tp2_r_multiple * r if signal == Signal.BUY else entry - cfg.tp2_r_multiple * r
        return [tp1, tp2]

    def get_position_size(
        self,
        ctx: StrategyContext,
        entry: float,
        stop: float,
        signal: Signal,
    ) -> float:
        """
        Position size in units using risk-per-trade percent over stop distance.

        This is a structural default; the dedicated risk module may override.

        Args:
            ctx: Context with ``account_equity``.
            entry: Entry price.
            stop: Stop price.
            signal: Current signal.

        Returns:
            Position size (units); ``0`` when flat or invalid distance.
        """

        if signal == Signal.FLAT:
            return 0.0
        risk_amt = ctx.account_equity * CONFIG.risk.risk_per_trade_pct / 100.0
        dist = abs(entry - stop)
        if dist <= 0:
            return 0.0
        return risk_amt / dist

    def is_valid(self, ctx: StrategyContext) -> bool:
        """
        Pre-trade checks: data length, spread vs average, minimum ATR.

        Args:
            ctx: Context; ``avg_spread`` optional for relative spread filter.

        Returns:
            True if the strategy is allowed to propose a new trade.
        """

        if len(ctx.df) < 30:
            return False
        if ctx.avg_spread is not None and ctx.avg_spread > 0:
            if ctx.spread > CONFIG.risk.spread_multiplier_skip * ctx.avg_spread:
                return False
        close = ctx.df["close"]
        if not pd.api.types.is_numeric_dtype(close):
            return False
        return bool(pd.notna(close.iloc[-1]))
