import pandas as pd

from core.position_sizing import calculate_shares
from core.risk import PositionState, check_risk_stops
from strategy.engine import Strategy


class Backtester:
    """Simple historical simulator.

    Walks through a price DataFrame bar-by-bar, asks the Strategy for a
    signal, and simulates BUY/SELL fills at the close of that bar.
    Long-only, percent-of-cash sizing, no commissions/slippage.

    Risk stops (trailing + time) come from core.risk and are shared with
    the live trading loop in main.py.
    """

    def __init__(
        self,
        strategy: Strategy,
        starting_cash: float = 100_000.0,
        position_pct: float = 0.95,
        trailing_stop_pct: float = 0.05,
        max_hold_bars: int = 15,
    ):
        self.strategy = strategy
        self.starting_cash = starting_cash
        self.position_pct = position_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_hold_bars = max_hold_bars

    def run(self, price_dataframe: pd.DataFrame) -> dict:
        cash_balance = self.starting_cash
        position_state: PositionState | None = None
        trade_log: list[dict] = []

        # Skip warm-up bars where the strategy can't produce a real signal.
        first_evaluable_index = self.strategy.LONG_WINDOW + 1

        for bar_index in range(first_evaluable_index, len(price_dataframe)):
            window = price_dataframe.iloc[: bar_index + 1]
            current_close = float(window["Close"].iloc[-1])
            bar_time = window.index[-1]

            # ----------------------------------------------------------
            # RISK CHECKS — run BEFORE the strategy so stops have priority
            # over any new BUY/SELL signal on this bar.
            # ----------------------------------------------------------
            if position_state is not None:
                position_state.tick()
                position_state.update_trailing_high(current_close)

                stop_reason = check_risk_stops(
                    position_state=position_state,
                    current_price=current_close,
                    trailing_stop_pct=self.trailing_stop_pct,
                    max_hold_bars=self.max_hold_bars,
                )
                if stop_reason is not None:
                    cash_balance += position_state.shares * current_close
                    trade_log.append({
                        "time": bar_time,
                        "action": stop_reason,
                        "price": current_close,
                        "shares": position_state.shares,
                        "pnl": position_state.realized_pnl_at(current_close),
                    })
                    position_state = None
                    continue

            # ----------------------------------------------------------
            # STRATEGY SIGNAL — only reached if no stop fired this bar.
            # ----------------------------------------------------------
            signal = self.strategy.generate_signals(window)

            if signal == "BUY" and position_state is None:
                shares_to_buy = calculate_shares(cash_balance, current_close, self.position_pct)
                if shares_to_buy <= 0:
                    continue
                cash_balance -= shares_to_buy * current_close
                position_state = PositionState(
                    shares=shares_to_buy,
                    entry_price=current_close,
                    highest_price_since_entry=current_close,
                )
                trade_log.append({
                    "time": bar_time,
                    "action": "BUY",
                    "price": current_close,
                    "shares": shares_to_buy,
                    "pnl": None,
                })
            elif signal == "SELL" and position_state is not None:
                cash_balance += position_state.shares * current_close
                trade_log.append({
                    "time": bar_time,
                    "action": "SELL",
                    "price": current_close,
                    "shares": position_state.shares,
                    "pnl": position_state.realized_pnl_at(current_close),
                })
                position_state = None

        final_close = float(price_dataframe["Close"].iloc[-1])
        open_position_shares = position_state.shares if position_state is not None else 0
        final_equity = cash_balance + open_position_shares * final_close

        completed_trades = [trade for trade in trade_log if trade["pnl"] is not None]
        winning_trades = [trade for trade in completed_trades if trade["pnl"] > 0]
        win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0.0
        total_return = (final_equity - self.starting_cash) / self.starting_cash

        return {
            "num_signals": len(trade_log),
            "num_completed_trades": len(completed_trades),
            "win_rate": win_rate,
            "starting_cash": self.starting_cash,
            "final_equity": final_equity,
            "total_return": total_return,
            "open_position_shares": open_position_shares,
            "trade_log": trade_log,
        }
