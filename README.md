# Trading Bot

Automated trading bot in Python using the native Interactive Brokers TWS API (`ibapi`) and pandas. Runs against **Trader Workstation (TWS) paper trading** on port **7497**.

## Architecture

ibapi is entirely **asynchronous and event-driven** — there are no blocking request/response pairs. The bot uses a multithreaded design:

- **`EClient.run()`** runs on a background daemon thread.
- **Callbacks** (`EWrapper`) handle incoming data on the API thread.
- The **main thread** runs strategy logic and waits on `threading.Event` signals (e.g. `nextValidId`, historical data complete) instead of polling.
- Shared bar data is protected with a **`threading.Lock`** in `DataHandler`.

```
Main thread                          API thread (app.run())
───────────                          ──────────────────────
connect + start thread
connected_event.wait()  ───────────► nextValidId → set event
reqHistoricalData()     ───────────► historicalData → add_bar()
                                     historicalDataEnd → set event
get_dataframe() + strategy
```

## Project structure

| File | Purpose |
|------|---------|
| `config.py` | Connection settings, target tickers, default order size |
| `api/ib_client.py` | `IBClient(EWrapper, EClient)` — connection callbacks and message routing |
| `core/contracts.py` | `create_us_stock()` — SMART-routed US stock contracts |
| `core/orders.py` | `create_market_order()` — market order factory |
| `core/data_handler.py` | Thread-safe bar buffer → pandas DataFrame |
| `strategy/engine.py` | 9/21 SMA crossover strategy (indicators separated from rules) |
| `main.py` | Entry point — connect, request data, run strategy |

## Requirements

- Python 3.9+
- TWS or IB Gateway with **API enabled** (paper port **7497**)
- Packages: `ibapi`, `pandas`

```bash
pip install ibapi pandas
```

## TWS setup

1. Open TWS and log into your **paper trading** account.
2. Go to **Edit → Global Configuration → API → Settings**.
3. Enable **"ActiveX and Socket Clients"**.
4. Confirm socket port is **7497** (default for paper).

## Run

```bash
python main.py
```

Expected output once connected and data is downloaded:

```
Historical data download complete | reqId=1 | ...
AAPL | bars=60 | signal=HOLD
```

## Strategy

Simple **moving average crossover** (trend-following):

- 9-period SMA (fast) and 21-period SMA (slow) on `Close`
- **BUY** when the 9 crosses above the 21
- **SELL** when the 9 crosses below the 21
- **HOLD** otherwise

Indicators and rules are split in `strategy/engine.py` so either can be swapped independently.

## API reference

- [IBKR Campus — TWS API](https://www.interactivebrokers.com/campus/ibkr-api-page/trader-workstation-api/)
- [TWS API class reference](https://interactivebrokers.github.io/tws-api/)

## Disclaimer

For educational and paper-trading use only. Not financial advice.
