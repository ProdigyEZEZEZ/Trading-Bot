TWS_HOST = "127.0.0.1"
TWS_PORT = 7497

# Each script that connects to TWS needs a unique client ID (same host/port).
LIVE_CLIENT_ID = 1       # main.py — live paper trading
DOWNLOAD_CLIENT_ID = 2   # download_data.py — one-shot historical download

TARGET_TICKERS = ["NVDA", "MSFT", "GOOGL", "NVDA", "META"]

# Position sizing — fraction of available cash to deploy per trade.
# Common rule of thumb for a single-asset long-only bot is 0.90–1.00.
# Drop it lower (e.g. 0.50) to keep dry powder for slippage, fees, or other trades.
POSITION_SIZE_PCT = 0.95

# Starting equity used by the backtester only (live uses the real TWS account).
STARTING_CASH = 100_000.0

# Risk management — applied to every open position in both backtest and live.
TRAILING_STOP_PCT = 0.29   # close the position if price falls this far from its peak
MAX_HOLD_BARS = 10        # close the position after this many completed bars
