from ibapi.contract import Contract


def create_us_stock(symbol: str) -> Contract:
    """Build a Smart-routed US stock contract for the given ticker symbol."""
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.primaryExchange = "NASDAQ"
    contract.currency = "USD"
    return contract
