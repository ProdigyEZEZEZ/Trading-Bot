import threading
import time

import config
from api.ib_client import IBClient
from core.contracts import create_us_stock
from strategy.engine import Strategy

HISTORICAL_REQ_ID = 1


def run_loop(app: IBClient) -> None:
    """Run the ibapi message loop. Executes on a background thread."""
    app.run()


def main() -> None:
    app = IBClient()
    app.connect(config.TWS_HOST, config.TWS_PORT, config.CLIENT_ID)

    threading.Thread(target=run_loop, args=(app,), daemon=True).start()

    # Wait for the handshake to complete (nextValidId sets this) before sending
    # requests, rather than guessing with a fixed sleep.
    if not app.connected_event.wait(timeout=10):
        print("Timed out waiting for TWS connection (nextValidId not received).")
        app.disconnect()
        return

    symbol = config.TARGET_TICKERS[0]
    contract = create_us_stock(symbol)

    app.data_handler.clear()
    app.historical_data_end_event.clear()
    app.reqHistoricalData(
        HISTORICAL_REQ_ID,
        contract,
        "",            # endDateTime: "" means now
        "3600 S",      # durationStr: 1 hour
        "1 min",       # barSizeSetting
        "TRADES",      # whatToShow
        1,             # useRTH: regular trading hours only
        1,             # formatDate: yyyymmdd HH:mm:ss
        False,         # keepUpToDate
        [],            # chartOptions
    )

    strategy = Strategy()
    signal_done = False

    while True:
        if app.historical_data_end_event.is_set() and not signal_done:
            df = app.data_handler.get_dataframe()
            signal = strategy.generate_signals(df)
            print(f"{symbol} | bars={len(df)} | signal={signal}")
            signal_done = True

        time.sleep(1)


if __name__ == "__main__":
    main()
