from ibapi.order import Order


def create_market_order(action: str, quantity: float) -> Order:
    """Build a simple market order. `action` must be 'BUY' or 'SELL'."""
    action = action.upper()
    if action not in ("BUY", "SELL"):
        raise ValueError(f"action must be 'BUY' or 'SELL', got {action!r}")

    order = Order()
    order.action = action
    order.orderType = "MKT"
    order.totalQuantity = quantity

    # ibapi 9.x defaults these to True, but TWS rejects them with error 10268.
    # Disable to keep orders compatible with current TWS builds.
    order.eTradeOnly = False
    order.firmQuoteOnly = False

    return order
