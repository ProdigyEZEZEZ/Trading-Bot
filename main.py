import threading

import config
from api.ib_client import IBClient
from core.contracts import create_us_stock
from core.orders import create_market_order
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

    if not app.historical_data_end_event.wait(timeout=60):
        print("Timed out waiting for historical data download.")
        app.disconnect()
        return

    df = app.data_handler.get_dataframe()
    signal = strategy.generate_signals(df)
    print(f"{symbol} | bars={len(df)} | signal={signal}")

    if signal in ("BUY", "SELL") and app.next_order_id is not None:
        order = create_market_order(signal, config.DEFAULT_ORDER_QUANTITY)
        order_id = app.next_order_id
        app.next_order_id += 1
        print(f"Placing {signal} {config.DEFAULT_ORDER_QUANTITY} {symbol} | orderId={order_id}")
        app.placeOrder(order_id, contract, order)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        app.disconnect()


if __name__ == "__main__":
    main()
