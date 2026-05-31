import threading

import config
from api.ib_client import IBClient
from core.contracts import create_us_stock
from core.orders import create_market_order
from core.position_sizing import calculate_shares
from core.risk import PositionState, check_risk_stops
from strategy.engine import Strategy

HISTORICAL_REQ_ID = 1
ACCOUNT_SUMMARY_REQ_ID = 9001
WARMUP_DURATION = "1 D"
BAR_SIZE = "10 secs"


def run_loop(ib_client: IBClient) -> None:
    """Run the ibapi message loop. Executes on a background thread."""
    ib_client.run()


def place_buy_order(
    ib_client: IBClient,
    contract,
    symbol: str,
    last_close: float,
) -> int:
    """Size a BUY off available cash and submit it. Returns share count placed
    (0 if the order was skipped)."""
    if ib_client.next_order_id is None or ib_client.available_cash is None:
        return 0

    shares = calculate_shares(ib_client.available_cash, last_close, config.POSITION_SIZE_PCT)
    if shares <= 0:
        print(
            f"Skip BUY {symbol}: cash=${ib_client.available_cash:.2f} "
            f"@ ${last_close:.2f} would size 0 shares"
        )
        return 0

    order = create_market_order("BUY", shares)
    order_id = ib_client.next_order_id
    ib_client.next_order_id += 1
    print(
        f"Placing BUY {shares} {symbol} @~${last_close:.2f} "
        f"(cash=${ib_client.available_cash:.2f}) | orderId={order_id}"
    )
    ib_client.placeOrder(order_id, contract, order)

    # Optimistic local decrement so back-to-back signals don't over-allocate.
    # TWS will push the authoritative balance via the account-summary feed.
    ib_client.available_cash -= shares * last_close
    return shares


def place_sell_order(
    ib_client: IBClient,
    contract,
    symbol: str,
    shares: int,
    last_close: float,
) -> bool:
    """Submit a SELL that closes out `shares`. Returns True on submission."""
    if ib_client.next_order_id is None or shares <= 0:
        return False

    order = create_market_order("SELL", shares)
    order_id = ib_client.next_order_id
    ib_client.next_order_id += 1
    print(f"Placing SELL {shares} {symbol} @~${last_close:.2f} | orderId={order_id}")
    ib_client.placeOrder(order_id, contract, order)

    if ib_client.available_cash is not None:
        ib_client.available_cash += shares * last_close
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

    # Subscribe to the cash balance. TWS keeps pushing updates on this rolling
    # subscription, so available_cash stays roughly fresh during the session.
    ib_client.account_summary_event.clear()
    ib_client.reqAccountSummary(ACCOUNT_SUMMARY_REQ_ID, "All", "TotalCashValue")
    if not ib_client.account_summary_event.wait(timeout=10):
        print("Timed out waiting for account summary from TWS.")
        ib_client.disconnect()
        return

    if ib_client.available_cash is None:
        print("Account summary returned but no TotalCashValue tag was provided.")
        ib_client.disconnect()
        return
    print(f"Account cash: ${ib_client.available_cash:,.2f}")

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

    position_state: PositionState | None = None
    last_seen_bar_time = None

    try:
        while True:
            ib_client.new_bar_event.wait()
            ib_client.new_bar_event.clear()

            price_dataframe = ib_client.data_handler.get_dataframe()
            if price_dataframe.empty:
                continue

            current_bar_time = price_dataframe.index[-1]
            is_new_bar = current_bar_time != last_seen_bar_time
            last_seen_bar_time = current_bar_time

            last_close = float(price_dataframe["Close"].iloc[-1])

            # ----------------------------------------------------------
            # RISK CHECKS — same logic the backtester uses, applied to
            # the live position. Tick bars_held only on completed bars so
            # mid-bar updates from TWS don't burn through MAX_HOLD_BARS.
            # ----------------------------------------------------------
            if position_state is not None:
                if is_new_bar:
                    position_state.tick()
                position_state.update_trailing_high(last_close)

                stop_reason = check_risk_stops(
                    position_state=position_state,
                    current_price=last_close,
                    trailing_stop_pct=config.TRAILING_STOP_PCT,
                    max_hold_bars=config.MAX_HOLD_BARS,
                )
                if stop_reason is not None:
                    print(f"{stop_reason} fired for {symbol} @ ${last_close:.2f}")
                    if place_sell_order(ib_client, contract, symbol, position_state.shares, last_close):
                        position_state = None
                    continue

            # ----------------------------------------------------------
            # STRATEGY SIGNAL — only reached if no stop fired this bar.
            # ----------------------------------------------------------
            signal = strategy.generate_signals(price_dataframe)

            if signal == "BUY" and position_state is None:
                shares_placed = place_buy_order(ib_client, contract, symbol, last_close)
                if shares_placed > 0:
                    position_state = PositionState(
                        shares=shares_placed,
                        entry_price=last_close,
                        highest_price_since_entry=last_close,
                    )
            elif signal == "SELL" and position_state is not None:
                if place_sell_order(ib_client, contract, symbol, position_state.shares, last_close):
                    position_state = None
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        ib_client.cancelAccountSummary(ACCOUNT_SUMMARY_REQ_ID)
        ib_client.disconnect()


if __name__ == "__main__":
    main()
