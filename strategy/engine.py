import pandas as pd


class Strategy:
    """Trading strategy: turns a price DataFrame into a BUY/SELL/HOLD signal."""

    SHORT_WINDOW = 9
    LONG_WINDOW = 21

    # ------------------------------------------------------------------
    # INDICATORS — pure math on the price data.
    # Swap or extend these without touching the rules below.
    # ------------------------------------------------------------------
    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["SMA_short"] = out["Close"].rolling(self.SHORT_WINDOW).mean()
        out["SMA_long"] = out["Close"].rolling(self.LONG_WINDOW).mean()
        return out

    # ------------------------------------------------------------------
    # RULES — convert the latest indicator values into a trade decision.
    # Replace this body to change the strategy; keep the return contract.
    # ------------------------------------------------------------------
    def _apply_rules(self, indicators: pd.DataFrame) -> str:
        if len(indicators) < self.LONG_WINDOW + 1:
            return "HOLD"

        prev = indicators.iloc[-2]
        curr = indicators.iloc[-1]

        if pd.isna(prev["SMA_long"]) or pd.isna(curr["SMA_long"]):
            return "HOLD"

        crossed_up = prev["SMA_short"] <= prev["SMA_long"] and curr["SMA_short"] > curr["SMA_long"]
        crossed_down = prev["SMA_short"] >= prev["SMA_long"] and curr["SMA_short"] < curr["SMA_long"]

        if crossed_up:
            return "BUY"
        if crossed_down:
            return "SELL"
        return "HOLD"

    def generate_signals(self, df: pd.DataFrame) -> str:
        """Return 'BUY', 'SELL', or 'HOLD' based on the latest bar."""
        indicators = self._compute_indicators(df)
        return self._apply_rules(indicators)
