import pandas as pd

from strategy.engine import Strategy


class Backtester:
    """Simple historical simulator.

    Walks through a price DataFrame bar-by-bar, asks the Strategy for a
    signal, and simulates BUY/SELL fills at the close of that bar.
    Long-only, fixed share quantity, no commissions/slippage.
    """

    def __init__(
        self,
        strategy: Strategy,
        starting_cash: float = 100_000.0,
        quantity: int = 100,
    ):
        self.strategy = strategy
        self.starting_cash = starting_cash
        self.quantity = quantity

    def run(self, price_dataframe: pd.DataFrame) -> dict:
        cash_balance = self.starting_cash
        position_shares = 0
        entry_price = None
        trade_log: list[dict] = []

        # Skip warm-up bars where the strategy can't produce a real signal.
        first_evaluable_index = self.strategy.LONG_WINDOW + 1

        for bar_index in range(first_evaluable_index, len(price_dataframe)):
            window = price_dataframe.iloc[: bar_index + 1]
            signal = self.strategy.generate_signals(window)
            current_close = float(window["Close"].iloc[-1])
            bar_time = window.index[-1]

            if signal == "BUY" and position_shares == 0:
                position_shares = self.quantity
                cash_balance -= position_shares * current_close
                entry_price = current_close
                trade_log.append({
                    "time": bar_time,
                    "action": "BUY",
                    "price": current_close,
                    "shares": position_shares,
                    "pnl": None,
                })
            elif signal == "SELL" and position_shares > 0:
                exit_price = current_close
                cash_balance += position_shares * exit_price
                realized_pnl = (exit_price - entry_price) * position_shares
                trade_log.append({
                    "time": bar_time,
                    "action": "SELL",
                    "price": exit_price,
                    "shares": position_shares,
                    "pnl": realized_pnl,
                })
                position_shares = 0
                entry_price = None

        final_close = float(price_dataframe["Close"].iloc[-1])
        final_equity = cash_balance + position_shares * final_close

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
            "open_position_shares": position_shares,
            "trade_log": trade_log,
        }
