import sys
from pathlib import Path

import pandas as pd

import config
from core.backtester import Backtester
from strategy.engine import Strategy


def load_price_dataframe(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found at {csv_path}. "
            f"Generate one with: python download_data.py"
        )
    price_dataframe = pd.read_csv(csv_path, parse_dates=["time"], index_col="time")
    return price_dataframe.sort_index()


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/historical.csv")

    price_dataframe = load_price_dataframe(csv_path)
    print(f"Loaded {len(price_dataframe)} bars from {csv_path}")
    print("risk management: trailing stop percentage =", config.TRAILING_STOP_PCT, "max hold bars =", config.MAX_HOLD_BARS)
    strategy = Strategy()
    backtester = Backtester(
        strategy=strategy,
        starting_cash=config.STARTING_CASH,
        position_pct=config.POSITION_SIZE_PCT,
        trailing_stop_pct=config.TRAILING_STOP_PCT,
        max_hold_bars=config.MAX_HOLD_BARS,
    )
    results = backtester.run(price_dataframe)

    print("=" * 60)
    print(f"Signals fired:       {results['num_signals']}")
    print(f"Completed trades:    {results['num_completed_trades']}")
    print(f"Win rate:            {results['win_rate']:.1%}")
    print(f"Starting cash:       ${results['starting_cash']:,.2f}")
    print(f"Final equity:        ${results['final_equity']:,.2f}")
    print(f"Total return:        {results['total_return']:+.2%}")
    print(f"Open position:       {results['open_position_shares']} shares")
    print("=" * 60)

    if results["trade_log"]:
        print("\nTrade log (last 10):")
        for trade in results["trade_log"][-10:]:
            pnl_str = f"pnl=${trade['pnl']:+,.2f}" if trade["pnl"] is not None else "pnl=—"
            print(f"  {trade['time']} | {trade['action']:4} @ ${trade['price']:.2f} x{trade['shares']} | {pnl_str}")


if __name__ == "__main__":
    main()
