"""
Trading strategies built on :class:`~forex_bot.strategies.base_strategy.BaseStrategy`.
"""

from forex_bot.strategies.arbitrage_strat import StatisticalArbitrageStrategy
from forex_bot.strategies.base_strategy import (
    BaseStrategy,
    Signal,
    StrategyContext,
)
from forex_bot.strategies.carry_trade_strat import CarryTradeStrategy
from forex_bot.strategies.event_driven_strat import EventDrivenStrategy
from forex_bot.strategies.mean_reversion_strat import MeanReversionStrategy
from forex_bot.strategies.ml_strat import MlStrategy
from forex_bot.strategies.multi_strategy import MultiStrategyHybrid
from forex_bot.strategies.momentum_strat import MomentumStrategy
from forex_bot.strategies.price_action_strat import PriceActionStrategy
from forex_bot.strategies.regime_detector import (
    MarketRegime,
    RegimeSwitcherStrategy,
    classify_regime,
)
from forex_bot.strategies.session_breakout_strat import SessionBreakoutStrategy
from forex_bot.strategies.smc_strat import SmcStrategy
from forex_bot.strategies.trend_following_strat import TrendFollowingStrategy
from forex_bot.strategies.volume_strat import VolumeWyckoffStrategy

__all__ = [
    "BaseStrategy",
    "CarryTradeStrategy",
    "EventDrivenStrategy",
    "MarketRegime",
    "MeanReversionStrategy",
    "MlStrategy",
    "MomentumStrategy",
    "MultiStrategyHybrid",
    "PriceActionStrategy",
    "RegimeSwitcherStrategy",
    "SessionBreakoutStrategy",
    "Signal",
    "SmcStrategy",
    "StatisticalArbitrageStrategy",
    "StrategyContext",
    "TrendFollowingStrategy",
    "VolumeWyckoffStrategy",
    "classify_regime",
]
