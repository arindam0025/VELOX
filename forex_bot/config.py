"""
Central configuration for the forex trading bot.

All tunable parameters, credentials (via environment), and operational modes
are defined here. Other modules must import settings from this module rather
than embedding literals.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

# Optional: load .env from project root if python-dotenv is available
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.is_file():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass


def _env_str(key: str, default: str) -> str:
    """Return environment variable or default."""

    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    """Parse boolean from environment (true/false/1/0)."""

    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    """Parse float from environment."""

    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(key: str, default: int) -> int:
    """Parse int from environment."""

    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_int_tuple(key: str, default_csv: str) -> tuple[int, ...]:
    """Parse comma-separated positive integers from environment."""

    raw = _env_str(key, default_csv)
    return tuple(int(x.strip()) for x in raw.split(",") if x.strip())


class AppMode(str, Enum):
    """High-level execution mode: backtest vs live."""

    BACKTEST = "backtest"
    LIVE = "live"


class BrokerName(str, Enum):
    """Supported broker connectors."""

    OANDA = "oanda"
    METATRADER5 = "metatrader5"
    CCXT = "ccxt"


class DataSource(str, Enum):
    """OHLCV / tick data providers."""

    OANDA = "oanda"
    METATRADER5 = "metatrader5"
    YFINANCE = "yfinance"


class CacheBackend(str, Enum):
    """Cache for bars and derived series."""

    REDIS = "redis"
    PARQUET = "parquet"
    NONE = "none"


class Timeframe(str, Enum):
    """Supported candle granularities (broker-agnostic labels)."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


@dataclass(frozen=True)
class PathsConfig:
    """Filesystem paths for logs, cache, models, and data."""

    project_root: Path
    log_dir: Path
    cache_dir: Path
    parquet_cache_dir: Path
    ml_models_dir: Path
    backtest_exports_dir: Path


@dataclass(frozen=True)
class SessionWindow:
    """Inclusive start hour and exclusive end hour in UTC (0–24 scale)."""

    start_hour_utc: int
    end_hour_utc: int


@dataclass(frozen=True)
class SessionConfig:
    """Forex session definitions (UTC)."""

    asian: SessionWindow
    london: SessionWindow
    new_york: SessionWindow
    london_ny_overlap: SessionWindow


@dataclass(frozen=True)
class RiskConfig:
    """Portfolio and per-trade risk limits."""

    risk_per_trade_pct: float
    max_open_trades: int
    max_correlated_group_risk_pct: float
    daily_loss_limit_pct: float
    max_drawdown_pct: float
    min_risk_reward: float
    preferred_rr_1: float
    preferred_rr_2: float
    tp1_fraction: float
    tp2_fraction: float
    spread_multiplier_skip: float
    news_blackout_before_minutes: int
    news_blackout_after_minutes: int


@dataclass(frozen=True)
class StopTakeProfitConfig:
    """Default multi-TP and ATR multiples."""

    atr_sl_multiplier: float
    tp1_r_multiple: float
    tp2_r_multiple: float


@dataclass(frozen=True)
class IndicatorThresholdsConfig:
    """Shared thresholds for indicators and regime logic."""

    adx_trend_threshold: float
    volume_zscore_threshold: float
    rsi_oversold: float
    rsi_overbought: float
    atr_percentile_low: float
    atr_percentile_high: float
    ml_confidence_threshold: float
    multi_strategy_min_score: float
    multi_strategy_weight_smc: float
    multi_strategy_weight_volume: float
    multi_strategy_weight_session: float
    multi_strategy_weight_trend: float
    stat_arb_z_entry: float
    retail_sentiment_extreme_pct: float


@dataclass(frozen=True)
class OandaConfig:
    """OANDA v20 REST API settings."""

    api_token: str
    account_id: str
    environment: str  # "practice" | "live"
    rest_base_url_practice: str
    rest_base_url_live: str
    stream_base_url_practice: str
    stream_base_url_live: str


@dataclass(frozen=True)
class MetaTrader5Config:
    """MetaTrader 5 terminal connection."""

    login: int
    password: str
    server: str
    path: str


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL via SQLAlchemy."""

    url: str
    echo_sql: bool
    pool_size: int
    max_overflow: int


@dataclass(frozen=True)
class RedisConfig:
    """Redis connection for caching."""

    url: str
    db: int
    socket_timeout_seconds: float


@dataclass(frozen=True)
class TelegramConfig:
    """Telegram bot alerts."""

    bot_token: str
    chat_id: str
    enabled: bool


@dataclass(frozen=True)
class EmailConfig:
    """SMTP email for critical alerts."""

    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_addr: str
    to_addrs: tuple[str, ...]
    use_tls: bool
    enabled: bool


@dataclass(frozen=True)
class SchedulerConfig:
    """APScheduler defaults."""

    timezone: str
    misfire_grace_seconds: int


@dataclass(frozen=True)
class MLConfig:
    """Machine learning pipeline defaults."""

    label_forward_return_high_pct: float
    label_forward_return_low_pct: float
    train_window_months: int
    retrain_interval_days: int
    use_optuna: bool
    use_mlflow: bool
    enable_rl: bool
    lstm_sequence_length: int
    xgb_random_state: int


@dataclass(frozen=True)
class BacktestConfig:
    """Backtesting engine defaults."""

    initial_capital: float
    monte_carlo_runs: int
    commission_per_million_usd: float
    swap_long_short_pips_per_lot_per_night: tuple[float, float]


@dataclass(frozen=True)
class CorrelationGroupsConfig:
    """Currency buckets for correlated exposure limits."""

    eur_block: tuple[str, ...]
    usd_block: tuple[str, ...]


@dataclass(frozen=True)
class IndicatorParamsConfig:
    """Periods and structural parameters for technical indicators."""

    ema_periods: tuple[int, ...]
    sma_periods: tuple[int, ...]
    rsi_period: int
    rsi_divergence_lookback: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    bb_period: int
    bb_std: float
    bb_bandwidth_percentile_window: int
    atr_period_short: int
    atr_period_long: int
    atr_regime_window: int
    adx_period: int
    pivot_left_right: int
    swing_lookback: int
    trendline_min_swings: int
    trendline_regression_window: int
    volume_profile_bins: int
    volume_profile_window: int
    volume_ma_period: int
    volume_divergence_lookback: int
    fvg_min_gap_atr_ratio: float
    order_block_impulse_atr_ratio: float
    bos_structure_lookback: int
    choch_confirm_bars: int
    liquidity_equal_tolerance_atr_ratio: float
    round_number_step_major: float
    round_number_step_minor: float
    intermarket_rolling_window: int
    session_breakout_volume_ma_ratio: float
    range_breakout_lookback: int
    wyckoff_volume_window: int
    dom_imbalance_levels: int


@dataclass(frozen=True)
class ForexConventionConfig:
    """Pip sizes for position and stop-distance math (major vs JPY)."""

    pip_size_non_jpy: float
    pip_size_jpy: float


@dataclass(frozen=True)
class CarryYieldConfig:
    """Annualized policy-rate proxies for carry ranking (percent per year)."""

    annual_yield_percent_by_ccy: dict[str, float]


@dataclass(frozen=True)
class StrategyDefaultsConfig:
    """Default instruments and cadence for statistical arbitrage and carry."""

    stat_arb_leg_a: str
    stat_arb_leg_b: str
    carry_rebalance_days: int


@dataclass(frozen=True)
class DataConfig:
    """Data acquisition, caching, and streaming defaults."""

    oanda_max_candles_per_request: int
    fetch_max_retries: int
    fetch_retry_backoff_seconds: float
    fetch_http_timeout_seconds: float
    redis_ohlcv_ttl_seconds: int
    parquet_cache_enabled: bool
    websocket_reconnect_delay_seconds: float
    websocket_heartbeat_seconds: float
    mt5_symbol_from_instrument: bool
    yfinance_auto_adjust: bool


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    mode: AppMode
    timezone: str
    pairs: tuple[str, ...]
    timeframes: tuple[Timeframe, ...]
    default_timeframe: Timeframe
    primary_broker: BrokerName
    fallback_data_source: DataSource
    cache_backend: CacheBackend
    paths: PathsConfig
    sessions: SessionConfig
    risk: RiskConfig
    stops_tp: StopTakeProfitConfig
    thresholds: IndicatorThresholdsConfig
    oanda: OandaConfig
    mt5: MetaTrader5Config
    database: DatabaseConfig
    redis: RedisConfig
    telegram: TelegramConfig
    email: EmailConfig
    scheduler: SchedulerConfig
    ml: MLConfig
    backtest: BacktestConfig
    correlation_groups: CorrelationGroupsConfig
    data: DataConfig
    indicator_params: IndicatorParamsConfig
    forex_convention: ForexConventionConfig
    carry_yields: CarryYieldConfig
    strategy_defaults: StrategyDefaultsConfig
    log_level: str
    log_json: bool
    log_to_console: bool
    log_rotation_when: str
    log_rotation_interval: int
    log_backup_count: int


def _default_pairs() -> tuple[str, ...]:
    """Default tradable pairs (OANDA-style naming)."""

    return (
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "USD_CAD",
        "NZD_USD",
    )


def _default_timeframes() -> tuple[Timeframe, ...]:
    """Default multi-timeframe set."""

    return (
        Timeframe.M1,
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.M30,
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.D1,
    )


def build_paths(project_root: Path | None = None) -> PathsConfig:
    """Construct path configuration relative to repository root."""

    root = project_root or Path(__file__).resolve().parent.parent
    base = root / "forex_bot_data"
    return PathsConfig(
        project_root=root,
        log_dir=Path(_env_str("FOREX_BOT_LOG_DIR", str(base / "logs"))),
        cache_dir=Path(_env_str("FOREX_BOT_CACHE_DIR", str(base / "cache"))),
        parquet_cache_dir=Path(
            _env_str("FOREX_BOT_PARQUET_DIR", str(base / "parquet"))
        ),
        ml_models_dir=Path(_env_str("FOREX_BOT_MODELS_DIR", str(base / "models"))),
        backtest_exports_dir=Path(
            _env_str("FOREX_BOT_BACKTEST_EXPORT_DIR", str(base / "backtest_exports"))
        ),
    )


def load_config() -> AppConfig:
    """
    Load full application configuration from defaults and environment.

    Returns:
        Immutable AppConfig used across the codebase.
    """

    mode = AppMode(_env_str("FOREX_BOT_MODE", AppMode.BACKTEST.value).lower())
    paths = build_paths()

    pairs_raw = _env_str("FOREX_BOT_PAIRS", "")
    pairs: tuple[str, ...] = (
        tuple(p.strip() for p in pairs_raw.split(",") if p.strip())
        if pairs_raw.strip()
        else _default_pairs()
    )

    tf_raw = _env_str("FOREX_BOT_TIMEFRAMES", "")
    if tf_raw.strip():
        timeframes = tuple(Timeframe(p.strip()) for p in tf_raw.split(",") if p.strip())
    else:
        timeframes = _default_timeframes()

    default_tf = Timeframe(_env_str("FOREX_BOT_DEFAULT_TIMEFRAME", Timeframe.H1.value))

    sessions = SessionConfig(
        asian=SessionWindow(
            start_hour_utc=_env_int("SESSION_ASIAN_START_UTC", 0),
            end_hour_utc=_env_int("SESSION_ASIAN_END_UTC", 8),
        ),
        london=SessionWindow(
            start_hour_utc=_env_int("SESSION_LONDON_START_UTC", 7),
            end_hour_utc=_env_int("SESSION_LONDON_END_UTC", 16),
        ),
        new_york=SessionWindow(
            start_hour_utc=_env_int("SESSION_NY_START_UTC", 12),
            end_hour_utc=_env_int("SESSION_NY_END_UTC", 21),
        ),
        london_ny_overlap=SessionWindow(
            start_hour_utc=_env_int("SESSION_OVERLAP_START_UTC", 12),
            end_hour_utc=_env_int("SESSION_OVERLAP_END_UTC", 16),
        ),
    )

    risk = RiskConfig(
        risk_per_trade_pct=_env_float("RISK_PER_TRADE_PCT", 1.0),
        max_open_trades=_env_int("MAX_OPEN_TRADES", 5),
        max_correlated_group_risk_pct=_env_float("MAX_CORRELATED_GROUP_RISK_PCT", 3.0),
        daily_loss_limit_pct=_env_float("DAILY_LOSS_LIMIT_PCT", 3.0),
        max_drawdown_pct=_env_float("MAX_DRAWDOWN_PCT", 10.0),
        min_risk_reward=_env_float("MIN_RISK_REWARD", 1.5),
        preferred_rr_1=_env_float("PREFERRED_RR_1", 2.0),
        preferred_rr_2=_env_float("PREFERRED_RR_2", 3.0),
        tp1_fraction=_env_float("TP1_POSITION_FRACTION", 0.5),
        tp2_fraction=_env_float("TP2_POSITION_FRACTION", 0.5),
        spread_multiplier_skip=_env_float("SPREAD_MULTIPLIER_SKIP", 2.0),
        news_blackout_before_minutes=_env_int("NEWS_BLACKOUT_BEFORE_MINUTES", 15),
        news_blackout_after_minutes=_env_int("NEWS_BLACKOUT_AFTER_MINUTES", 30),
    )

    stops_tp = StopTakeProfitConfig(
        atr_sl_multiplier=_env_float("ATR_SL_MULTIPLIER", 1.5),
        tp1_r_multiple=_env_float("TP1_R_MULTIPLE", 1.5),
        tp2_r_multiple=_env_float("TP2_R_MULTIPLE", 2.5),
    )

    thresholds = IndicatorThresholdsConfig(
        adx_trend_threshold=_env_float("ADX_TREND_THRESHOLD", 25.0),
        volume_zscore_threshold=_env_float("VOLUME_ZSCORE_THRESHOLD", 2.0),
        rsi_oversold=_env_float("RSI_OVERSOLD", 30.0),
        rsi_overbought=_env_float("RSI_OVERBOUGHT", 70.0),
        atr_percentile_low=_env_float("ATR_PERCENTILE_LOW", 33.0),
        atr_percentile_high=_env_float("ATR_PERCENTILE_HIGH", 66.0),
        ml_confidence_threshold=_env_float("ML_CONFIDENCE_THRESHOLD", 0.70),
        multi_strategy_min_score=_env_float("MULTI_STRATEGY_MIN_SCORE", 0.65),
        multi_strategy_weight_smc=_env_float("MULTI_STRATEGY_WEIGHT_SMC", 0.35),
        multi_strategy_weight_volume=_env_float("MULTI_STRATEGY_WEIGHT_VOLUME", 0.25),
        multi_strategy_weight_session=_env_float(
            "MULTI_STRATEGY_WEIGHT_SESSION", 0.20
        ),
        multi_strategy_weight_trend=_env_float("MULTI_STRATEGY_WEIGHT_TREND", 0.20),
        stat_arb_z_entry=_env_float("STAT_ARB_Z_ENTRY", 2.0),
        retail_sentiment_extreme_pct=_env_float("RETAIL_SENTIMENT_EXTREME_PCT", 70.0),
    )

    oanda_env = _env_str("OANDA_ENVIRONMENT", "practice").lower()
    oanda = OandaConfig(
        api_token=_env_str("OANDA_API_TOKEN", ""),
        account_id=_env_str("OANDA_ACCOUNT_ID", ""),
        environment=oanda_env,
        rest_base_url_practice=_env_str(
            "OANDA_REST_URL_PRACTICE", "https://api-fxpractice.oanda.com"
        ),
        rest_base_url_live=_env_str(
            "OANDA_REST_URL_LIVE", "https://api-fxtrade.oanda.com"
        ),
        stream_base_url_practice=_env_str(
            "OANDA_STREAM_URL_PRACTICE", "https://stream-fxpractice.oanda.com"
        ),
        stream_base_url_live=_env_str(
            "OANDA_STREAM_URL_LIVE", "https://stream-fxtrade.oanda.com"
        ),
    )

    mt5_login_raw = _env_str("MT5_LOGIN", "0")
    mt5 = MetaTrader5Config(
        login=int(mt5_login_raw) if mt5_login_raw.strip() else 0,
        password=_env_str("MT5_PASSWORD", ""),
        server=_env_str("MT5_SERVER", ""),
        path=_env_str("MT5_PATH", ""),
    )

    database = DatabaseConfig(
        url=_env_str(
            "DATABASE_URL",
            "postgresql+psycopg2://user:pass@localhost:5432/forex_bot",
        ),
        echo_sql=_env_bool("DATABASE_ECHO", False),
        pool_size=_env_int("DATABASE_POOL_SIZE", 5),
        max_overflow=_env_int("DATABASE_MAX_OVERFLOW", 10),
    )

    redis = RedisConfig(
        url=_env_str("REDIS_URL", "redis://localhost:6379/0"),
        db=_env_int("REDIS_DB", 0),
        socket_timeout_seconds=_env_float("REDIS_SOCKET_TIMEOUT", 5.0),
    )

    email_to = _env_str("EMAIL_TO", "")
    email = EmailConfig(
        smtp_host=_env_str("SMTP_HOST", ""),
        smtp_port=_env_int("SMTP_PORT", 587),
        username=_env_str("SMTP_USERNAME", ""),
        password=_env_str("SMTP_PASSWORD", ""),
        from_addr=_env_str("EMAIL_FROM", ""),
        to_addrs=tuple(x.strip() for x in email_to.split(",") if x.strip()),
        use_tls=_env_bool("SMTP_USE_TLS", True),
        enabled=_env_bool("EMAIL_ALERTS_ENABLED", False),
    )

    telegram = TelegramConfig(
        bot_token=_env_str("TELEGRAM_BOT_TOKEN", ""),
        chat_id=_env_str("TELEGRAM_CHAT_ID", ""),
        enabled=_env_bool("TELEGRAM_ALERTS_ENABLED", False),
    )

    scheduler = SchedulerConfig(
        timezone=_env_str("SCHEDULER_TIMEZONE", "UTC"),
        misfire_grace_seconds=_env_int("SCHEDULER_MISFIRE_GRACE_SECONDS", 30),
    )

    ml = MLConfig(
        label_forward_return_high_pct=_env_float("ML_LABEL_HIGH_PCT", 0.5),
        label_forward_return_low_pct=_env_float("ML_LABEL_LOW_PCT", -0.5),
        train_window_months=_env_int("ML_TRAIN_WINDOW_MONTHS", 6),
        retrain_interval_days=_env_int("ML_RETRAIN_INTERVAL_DAYS", 7),
        use_optuna=_env_bool("ML_USE_OPTUNA", True),
        use_mlflow=_env_bool("ML_USE_MLFLOW", False),
        enable_rl=_env_bool("ML_ENABLE_RL", False),
        lstm_sequence_length=_env_int("ML_LSTM_SEQUENCE_LENGTH", 64),
        xgb_random_state=_env_int("ML_XGB_RANDOM_STATE", 42),
    )

    backtest = BacktestConfig(
        initial_capital=_env_float("BACKTEST_INITIAL_CAPITAL", 100_000.0),
        monte_carlo_runs=_env_int("MONTE_CARLO_RUNS", 1000),
        commission_per_million_usd=_env_float("BACKTEST_COMMISSION_PER_MILLION_USD", 0.0),
        swap_long_short_pips_per_lot_per_night=(
            _env_float("BACKTEST_SWAP_LONG_PIPS", 0.0),
            _env_float("BACKTEST_SWAP_SHORT_PIPS", 0.0),
        ),
    )

    correlation_groups = CorrelationGroupsConfig(
        eur_block=tuple(
            p.strip()
            for p in _env_str(
                "CORR_GROUP_EUR",
                "EUR_USD,EUR_GBP,EUR_JPY,EUR_CHF,EUR_AUD,EUR_CAD,EUR_NZD",
            ).split(",")
            if p.strip()
        ),
        usd_block=tuple(
            p.strip()
            for p in _env_str(
                "CORR_GROUP_USD",
                "EUR_USD,GBP_USD,USD_JPY,USD_CHF,AUD_USD,USD_CAD,NZD_USD",
            ).split(",")
            if p.strip()
        ),
    )

    data = DataConfig(
        oanda_max_candles_per_request=_env_int("OANDA_MAX_CANDLES_PER_REQUEST", 5000),
        fetch_max_retries=_env_int("FETCH_MAX_RETRIES", 5),
        fetch_retry_backoff_seconds=_env_float("FETCH_RETRY_BACKOFF_SECONDS", 1.0),
        fetch_http_timeout_seconds=_env_float("FETCH_HTTP_TIMEOUT_SECONDS", 30.0),
        redis_ohlcv_ttl_seconds=_env_int("REDIS_OHLCV_TTL_SECONDS", 3600),
        parquet_cache_enabled=_env_bool("PARQUET_CACHE_ENABLED", True),
        websocket_reconnect_delay_seconds=_env_float(
            "WEBSOCKET_RECONNECT_DELAY_SECONDS", 5.0
        ),
        websocket_heartbeat_seconds=_env_float("WEBSOCKET_HEARTBEAT_SECONDS", 30.0),
        mt5_symbol_from_instrument=_env_bool("MT5_SYMBOL_FROM_INSTRUMENT", True),
        yfinance_auto_adjust=_env_bool("YFINANCE_AUTO_ADJUST", False),
    )

    indicator_params = IndicatorParamsConfig(
        ema_periods=_env_int_tuple("EMA_PERIODS", "8,21,50,100,200"),
        sma_periods=_env_int_tuple("SMA_PERIODS", "20,50,200"),
        rsi_period=_env_int("RSI_PERIOD", 14),
        rsi_divergence_lookback=_env_int("RSI_DIVERGENCE_LOOKBACK", 5),
        macd_fast=_env_int("MACD_FAST", 12),
        macd_slow=_env_int("MACD_SLOW", 26),
        macd_signal=_env_int("MACD_SIGNAL", 9),
        bb_period=_env_int("BB_PERIOD", 20),
        bb_std=_env_float("BB_STD", 2.0),
        bb_bandwidth_percentile_window=_env_int("BB_BANDWIDTH_PERCENTILE_WINDOW", 100),
        atr_period_short=_env_int("ATR_PERIOD_SHORT", 14),
        atr_period_long=_env_int("ATR_PERIOD_LONG", 21),
        atr_regime_window=_env_int("ATR_REGIME_WINDOW", 100),
        adx_period=_env_int("ADX_PERIOD", 14),
        pivot_left_right=_env_int("PIVOT_LEFT_RIGHT", 3),
        swing_lookback=_env_int("SWING_LOOKBACK", 5),
        trendline_min_swings=_env_int("TRENDLINE_MIN_SWINGS", 3),
        trendline_regression_window=_env_int("TRENDLINE_REGRESSION_WINDOW", 20),
        volume_profile_bins=_env_int("VOLUME_PROFILE_BINS", 64),
        volume_profile_window=_env_int("VOLUME_PROFILE_WINDOW", 100),
        volume_ma_period=_env_int("VOLUME_MA_PERIOD", 20),
        volume_divergence_lookback=_env_int("VOLUME_DIVERGENCE_LOOKBACK", 10),
        fvg_min_gap_atr_ratio=_env_float("FVG_MIN_GAP_ATR_RATIO", 0.15),
        order_block_impulse_atr_ratio=_env_float("ORDER_BLOCK_IMPULSE_ATR_RATIO", 1.2),
        bos_structure_lookback=_env_int("BOS_STRUCTURE_LOOKBACK", 10),
        choch_confirm_bars=_env_int("CHOCH_CONFIRM_BARS", 3),
        liquidity_equal_tolerance_atr_ratio=_env_float(
            "LIQUIDITY_EQUAL_TOLERANCE_ATR_RATIO", 0.1
        ),
        round_number_step_major=_env_float("ROUND_NUMBER_STEP_MAJOR", 1.0),
        round_number_step_minor=_env_float("ROUND_NUMBER_STEP_MINOR", 0.5),
        intermarket_rolling_window=_env_int("INTERMARKET_ROLLING_WINDOW", 60),
        session_breakout_volume_ma_ratio=_env_float(
            "SESSION_BREAKOUT_VOLUME_MA_RATIO", 1.2
        ),
        range_breakout_lookback=_env_int("RANGE_BREAKOUT_LOOKBACK", 20),
        wyckoff_volume_window=_env_int("WYCKOFF_VOLUME_WINDOW", 30),
        dom_imbalance_levels=_env_int("DOM_IMBALANCE_LEVELS", 10),
    )

    _carry_json = _env_str(
        "CARRY_ANNUAL_YIELDS_JSON",
        '{"USD":5.25,"EUR":4.0,"GBP":4.75,"JPY":0.1,"AUD":4.25,"NZD":5.0,"CAD":4.5,"CHF":1.5}',
    )
    carry_yields = CarryYieldConfig(
        annual_yield_percent_by_ccy=dict(json.loads(_carry_json)),
    )

    forex_convention = ForexConventionConfig(
        pip_size_non_jpy=_env_float("FOREX_PIP_SIZE_NON_JPY", 0.0001),
        pip_size_jpy=_env_float("FOREX_PIP_SIZE_JPY", 0.01),
    )

    strategy_defaults = StrategyDefaultsConfig(
        stat_arb_leg_a=_env_str("STAT_ARB_INSTRUMENT_A", "EUR_USD"),
        stat_arb_leg_b=_env_str("STAT_ARB_INSTRUMENT_B", "GBP_USD"),
        carry_rebalance_days=_env_int("CARRY_REBALANCE_DAYS", 7),
    )

    return AppConfig(
        mode=mode,
        timezone=_env_str("FOREX_BOT_TIMEZONE", "UTC"),
        pairs=pairs,
        timeframes=timeframes,
        default_timeframe=default_tf,
        primary_broker=BrokerName(
            _env_str("PRIMARY_BROKER", BrokerName.OANDA.value).lower()
        ),
        fallback_data_source=DataSource(
            _env_str("FALLBACK_DATA_SOURCE", DataSource.YFINANCE.value).lower()
        ),
        cache_backend=CacheBackend(
            _env_str("CACHE_BACKEND", CacheBackend.PARQUET.value).lower()
        ),
        paths=paths,
        sessions=sessions,
        risk=risk,
        stops_tp=stops_tp,
        thresholds=thresholds,
        oanda=oanda,
        mt5=mt5,
        database=database,
        redis=redis,
        telegram=telegram,
        email=email,
        scheduler=scheduler,
        ml=ml,
        backtest=backtest,
        correlation_groups=correlation_groups,
        data=data,
        indicator_params=indicator_params,
        forex_convention=forex_convention,
        carry_yields=carry_yields,
        strategy_defaults=strategy_defaults,
        log_level=_env_str("LOG_LEVEL", "INFO"),
        log_json=_env_bool("LOG_JSON", True),
        log_to_console=_env_bool("LOG_TO_CONSOLE", True),
        log_rotation_when=_env_str("LOG_ROTATION_WHEN", "midnight"),
        log_rotation_interval=_env_int("LOG_ROTATION_INTERVAL", 1),
        log_backup_count=_env_int("LOG_BACKUP_COUNT", 14),
    )


# Singleton configuration instance for import convenience
CONFIG: Final[AppConfig] = load_config()


def is_backtest_mode() -> bool:
    """Return True if the application is configured for backtesting."""

    return CONFIG.mode == AppMode.BACKTEST


def is_live_mode() -> bool:
    """Return True if the application is configured for live trading."""

    return CONFIG.mode == AppMode.LIVE
