"""Vectorized financial indicators built on Pandas + NumPy.

Each function takes a price Series or OHLCV DataFrame and returns a pd.Series
aligned to the input index. Functions are pure (no side effects, no I/O) so
they can be unit-tested in isolation and composed into strategies.

Conventions
-----------
- OHLCV DataFrames are expected to use the column names: "Open", "High",
  "Low", "Close", "Volume" (matches core.data_handler.DataHandler).
- "Wilder" smoothing uses alpha = 1 / window (RMA), the classic Welles
  Wilder convention used by RSI, ATR, ADX, etc.
- "Standard" EMA smoothing uses alpha = 2 / (window + 1).
- adjust=False is used everywhere so the recursion matches the textbook
  formulas (and matches how most charting platforms compute these).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """Simple (arithmetic) moving average.

    Equivalent to ``series.rolling(window).mean()``; wrapped here so every
    indicator lives in one module and strategies don't reach into pandas
    primitives directly.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    sma_series = series.rolling(window).mean()
    sma_series.name = f"SMA_{window}"
    return sma_series


def calculate_ewma(series: pd.Series, window: int, wilder: bool = False) -> pd.Series:
    """Exponentially-weighted moving average.

    Parameters
    ----------
    series : pd.Series
        Numeric series to smooth (e.g. closing prices, true range, gains).
    window : int
        Lookback period. Determines alpha.
    wilder : bool, default False
        If True, use Wilder's smoothing (alpha = 1 / window).
        If False, use the standard EMA convention (alpha = 2 / (window + 1)).

    Returns
    -------
    pd.Series
        EWMA aligned to the input index. NaN positions in the input propagate
        as NaN in the output until enough data exists for the recursion.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")

    alpha = 1.0 / window if wilder else 2.0 / (window + 1)
    return series.ewm(alpha=alpha, adjust=False).mean()


def calculate_rsi(price_dataframe: pd.DataFrame, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index on the Close column.

    RSI = 100 - 100 / (1 + RS), where RS = avg_gain / avg_loss and both
    averages are Wilder-smoothed (alpha = 1 / window).

    Edge cases
    ----------
    - avg_loss == 0 and avg_gain > 0  -> RSI = 100 (pure uptrend)
    - avg_loss == 0 and avg_gain == 0 -> RSI = 50  (no movement, neutral)
    - The first `window` bars are NaN because there isn't enough history.
    """
    close_prices = price_dataframe["Close"]
    price_change = close_prices.diff()

    gains = price_change.clip(lower=0.0)
    losses = -price_change.clip(upper=0.0)

    average_gain = calculate_ewma(gains, window, wilder=True)
    average_loss = calculate_ewma(losses, window, wilder=True)

    # Compute RS safely: where avg_loss == 0, fill with NaN, then patch.
    relative_strength = np.where(
        average_loss > 0,
        average_gain / average_loss.where(average_loss > 0),
        np.nan,
    )
    rsi_values = 100.0 - (100.0 / (1.0 + relative_strength))

    rsi_series = pd.Series(rsi_values, index=price_dataframe.index, name=f"RSI_{window}")

    # Patch the edge cases the ratio can't express.
    flat_mask = (average_gain == 0) & (average_loss == 0)
    pure_uptrend_mask = (average_loss == 0) & (average_gain > 0)
    rsi_series = rsi_series.mask(flat_mask, 50.0)
    rsi_series = rsi_series.mask(pure_uptrend_mask, 100.0)

    # The first `window` rows don't have enough data to seed the smoothing.
    rsi_series.iloc[:window] = np.nan
    return rsi_series


def calculate_atr(price_dataframe: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range, Wilder-smoothed.

    True Range for each bar is the maximum of:
        1. High - Low
        2. |High - previous Close|
        3. |Low  - previous Close|

    ATR is then Wilder's EWMA (alpha = 1 / window) of TR.
    """
    high_prices = price_dataframe["High"]
    low_prices = price_dataframe["Low"]
    previous_close = price_dataframe["Close"].shift(1)

    high_low_range = high_prices - low_prices
    high_prev_close_range = (high_prices - previous_close).abs()
    low_prev_close_range = (low_prices - previous_close).abs()

    true_range = pd.concat(
        [high_low_range, high_prev_close_range, low_prev_close_range],
        axis=1,
    ).max(axis=1)

    atr_series = calculate_ewma(true_range, window, wilder=True)
    atr_series.name = f"ATR_{window}"
    return atr_series


def _typical_price(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Bar representative price: (High + Low + Close) / 3.

    Standard input for VWAP — weights the bar's traded volume by where
    price actually traded, not just the closing print.
    """
    return (high + low + close) / 3.0


def calculate_vwap(price_dataframe: pd.DataFrame) -> pd.Series | None:
    """Volume-Weighted Average Price.

    VWAP = cumulative(typical_price * Volume) / cumulative(Volume),
    where typical_price = (High + Low + Close) / 3.

    Behaviour
    ---------
    - Returns None when no "Volume" column is present.
    - Requires "High", "Low", and "Close" columns for typical price.
    - If the index is a DatetimeIndex, the cumulative sums reset at the
      start of each calendar day so intraday VWAP behaves like the
      reference shown on most charting platforms.
    - Bars where cumulative volume is 0 yield NaN (avoids division by zero).
    """
    if "Volume" not in price_dataframe.columns:
        return None

    typical_prices = _typical_price(
        price_dataframe["High"],
        price_dataframe["Low"],
        price_dataframe["Close"],
    )
    volumes = price_dataframe["Volume"]
    price_volume_product = typical_prices * volumes

    if isinstance(price_dataframe.index, pd.DatetimeIndex):
        day_grouper = price_dataframe.index.normalize()
        cumulative_pv = price_volume_product.groupby(day_grouper).cumsum()
        cumulative_volume = volumes.groupby(day_grouper).cumsum()
    else:
        cumulative_pv = price_volume_product.cumsum()
        cumulative_volume = volumes.cumsum()

    # Safe divide: where volume sum is 0, return NaN instead of inf/error.
    vwap_series = cumulative_pv.divide(cumulative_volume.where(cumulative_volume > 0))
    vwap_series.name = "VWAP"
    return vwap_series


class RunningVWAP:
    """O(1) streaming VWAP for live trading.

    `calculate_vwap` runs a vectorized cumulative sum across the whole
    DataFrame — fine for backtests and plotting, but O(n) per call. In a
    live loop where you only want the latest value and a new bar arrives
    each minute, this class is constant-time per update.

    Resets at the start of each calendar day so intraday VWAP matches the
    behaviour of the vectorized helper above.

    Usage
    -----
        running_vwap = RunningVWAP()
        for bar_time, high, low, close, volume in stream:
            current_vwap = running_vwap.update(bar_time, high, low, close, volume)
    """

    def __init__(self) -> None:
        self._current_day: pd.Timestamp | None = None
        self._cumulative_price_volume: float = 0.0
        self._cumulative_volume: float = 0.0

    @property
    def value(self) -> float:
        """Latest VWAP, or NaN if no volume has been accumulated yet."""
        if self._cumulative_volume <= 0:
            return float("nan")
        return self._cumulative_price_volume / self._cumulative_volume

    def reset(self) -> None:
        self._current_day = None
        self._cumulative_price_volume = 0.0
        self._cumulative_volume = 0.0

    def update(
        self,
        bar_time: pd.Timestamp,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> float:
        """Fold a new bar into the running totals and return the latest VWAP."""
        bar_day = pd.Timestamp(bar_time).normalize()
        if bar_day != self._current_day:
            self._current_day = bar_day
            self._cumulative_price_volume = 0.0
            self._cumulative_volume = 0.0

        typical_price = (high + low + close) / 3.0
        self._cumulative_price_volume += typical_price * volume
        self._cumulative_volume += volume
        return self.value
