import threading

from ibapi.client import EClient
from ibapi.common import BarData
from ibapi.wrapper import EWrapper

from core.data_handler import DataHandler


class IBClient(EWrapper, EClient):
    """IB API client: connection callbacks and message routing only."""

    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None
        self.connected_event = threading.Event()
        self.data_handler = DataHandler()
        self.historical_data_end_event = threading.Event()

    def error(self, reqId, errorCode, errorString, *args, **kwargs):
        print(f"API Error | reqId={reqId} | code={errorCode} | {errorString}")

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.connected_event.set()

    def historicalData(self, reqId: int, bar: BarData):
        self.data_handler.add_bar(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        print(f"Historical data download complete | reqId={reqId} | {start} -> {end}")
        self.historical_data_end_event.set()

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(
            f"Order {orderId} | status={status} | filled={filled} | "
            f"remaining={remaining} | avgFillPrice={avgFillPrice}"
        )

    def openOrder(self, orderId, contract, order, orderState):
        print(f"Open order {orderId} | {contract.symbol} {order.action} {order.totalQuantity} {order.orderType}")

    def execDetails(self, reqId, contract, execution):
        print(f"Exec | {contract.symbol} | {execution.side} {execution.shares} @ {execution.price}")
