import threading

import config
from api.ib_client import IBClient
from core.contracts import create_us_stock
from core.orders import create_market_order
from strategy.engine import Strategy

HISTORICAL_REQ_ID = 1
WARMUP_DURATION = "1 D"
BAR_SIZE = "1 min"


def run_loop(ib_client: IBClient) -> None:
    """Run the ibapi message loop. Executes on a background thread."""
    ib_client.run()


def place_signal_order(
    ib_client: IBClient,
    contract,
    symbol: str,
    action: str,
) -> bool:
    """Build and send a market order. Returns True on submission."""
    if ib_client.next_order_id is None:
        return False
    order = create_market_order(action, config.DEFAULT_ORDER_QUANTITY)
    order_id = ib_client.next_order_id
    ib_client.next_order_id += 1
    print(f"Placing {action} {config.DEFAULT_ORDER_QUANTITY} {symbol} | orderId={order_id}")
    ib_client.placeOrder(order_id, contract, order)
    return True


def main() -> None:
    ib_client = IBClient()
    ib_client.connect(config.TWS_HOST, config.TWS_PORT, config.LIVE_CLIENT_ID)

    threading.Thread(target=run_loop, args=(ib_client,), daemon=True).start()

    # Wait for the handshake to complete (nextValidId sets this) before sending
    # requests, rather than guessing with a fixed sleep.
    if not ib_client.connected_event.wait(timeout=10):
        print("Timed out waiting for TWS connection (nextValidId not received).")
        ib_client.disconnect()
        return

    symbol = config.TARGET_TICKERS[0]
    contract = create_us_stock(symbol)

    ib_client.data_handler.clear()
    ib_client.historical_data_end_event.clear()
    ib_client.new_bar_event.clear()
    ib_client.reqHistoricalData(
        HISTORICAL_REQ_ID,
        contract,
        "",                # endDateTime: "" means now
        WARMUP_DURATION,   # durationStr: history pulled before live updates
        BAR_SIZE,          # barSizeSetting
        "TRADES",          # whatToShow
        1,                 # useRTH: regular trading hours only
        1,                 # formatDate: yyyymmdd HH:mm:ss
        True,              # keepUpToDate: switch to live updates after history
        [],                # chartOptions
    )

    if not ib_client.historical_data_end_event.wait(timeout=60):
        print("Timed out waiting for historical data download.")
        ib_client.disconnect()
        return

    strategy = Strategy()
    initial_dataframe = ib_client.data_handler.get_dataframe()
    print(f"Warm-up complete. {len(initial_dataframe)} bars loaded. Entering live loop for {symbol}.")

    current_position: str | None = None  # None or "LONG"

    try:
        while True:
            ib_client.new_bar_event.wait()
            ib_client.new_bar_event.clear()

            price_dataframe = ib_client.data_handler.get_dataframe()
            signal = strategy.generate_signals(price_dataframe)

            if signal == "BUY" and current_position != "LONG":
                if place_signal_order(ib_client, contract, symbol, "BUY"):
                    current_position = "LONG"
            elif signal == "SELL" and current_position == "LONG":
                if place_signal_order(ib_client, contract, symbol, "SELL"):
                    current_position = None
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        ib_client.disconnect()


if __name__ == "__main__":
    main()
