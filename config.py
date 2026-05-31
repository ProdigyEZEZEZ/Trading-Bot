TWS_HOST = "127.0.0.1"
TWS_PORT = 7497

# Each script that connects to TWS needs a unique client ID (same host/port).
LIVE_CLIENT_ID = 1       # main.py — live paper trading
DOWNLOAD_CLIENT_ID = 2   # download_data.py — one-shot historical download

TARGET_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]

DEFAULT_ORDER_QUANTITY = 100
