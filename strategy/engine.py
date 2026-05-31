import pandas as pd


class Strategy:
    """Trading strategy: turns a price DataFrame into a BUY/SELL/HOLD signal."""

    SHORT_WINDOW = 9
    LONG_WINDOW = 21

    # ------------------------------------------------------------------
    # INDICATORS — pure math on the price data.
    # Swap or extend these without touching the rules below.
    # ------------------------------------------------------------------
    def _compute_indicators(self, price_dataframe: pd.DataFrame) -> pd.DataFrame:
        indicator_dataframe = price_dataframe.copy()
        indicator_dataframe["SMA_short"] = indicator_dataframe["Close"].rolling(self.SHORT_WINDOW).mean()
        indicator_dataframe["SMA_long"] = indicator_dataframe["Close"].rolling(self.LONG_WINDOW).mean()
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
