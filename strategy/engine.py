import pandas as pd

from strategy.indicators import calculate_sma


class Strategy:
    """Trading strategy: turns a price DataFrame into a BUY/SELL/HOLD signal.

    Indicator math lives in `strategy.indicators` so this class only owns
    the rules — swap in EMA/RSI/ATR by changing `_compute_indicators` and
    adjusting `_apply_rules`, without touching any pandas internals here.
    """

    SHORT_WINDOW = 9
    LONG_WINDOW = 21

    # ------------------------------------------------------------------
    # INDICATORS — pull values out of strategy.indicators and attach them
    # to a copy of the price frame so the rules can read them by name.
    # ------------------------------------------------------------------
    def _compute_indicators(self, price_dataframe: pd.DataFrame) -> pd.DataFrame:
        indicator_dataframe = price_dataframe.copy()
        indicator_dataframe["SMA_short"] = calculate_sma(indicator_dataframe["Close"], self.SHORT_WINDOW)
        indicator_dataframe["SMA_long"] = calculate_sma(indicator_dataframe["Close"], self.LONG_WINDOW)
        return indicator_dataframe

    # ------------------------------------------------------------------
    # RULES — convert the latest indicator values into a trade decision.
    # Replace this body to change the strategy; keep the return contract.
    # ------------------------------------------------------------------
    def _apply_rules(self, indicator_dataframe: pd.DataFrame) -> str:
        if len(indicator_dataframe) < self.LONG_WINDOW + 1:
            return "HOLD"

        previous_bar = indicator_dataframe.iloc[-2]
        current_bar = indicator_dataframe.iloc[-1]

        if pd.isna(previous_bar["SMA_long"]) or pd.isna(current_bar["SMA_long"]):
            return "HOLD"

        crossed_up = (
            previous_bar["SMA_short"] < previous_bar["SMA_long"]
            and current_bar["SMA_short"] > current_bar["SMA_long"]
        )
        crossed_down = (
            previous_bar["SMA_short"] > previous_bar["SMA_long"]
            and current_bar["SMA_short"] < current_bar["SMA_long"]
        )

        if crossed_up:
            return "BUY"
        if crossed_down:
            return "SELL"
        return "HOLD"

    def generate_signals(self, price_dataframe: pd.DataFrame) -> str:
        """Return 'BUY', 'SELL', or 'HOLD' based on the latest bar."""
        indicator_dataframe = self._compute_indicators(price_dataframe)
        return self._apply_rules(indicator_dataframe)
