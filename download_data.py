import sys
import threading
from pathlib import Path

import config
from api.ib_client import IBClient
from core.contracts import create_us_stock

HISTORICAL_REQ_ID = 1
OUTPUT_DIR = Path("data")


def run_loop(ib_client: IBClient) -> None:
    ib_client.run()


def main() -> None:
    duration_str = sys.argv[1] if len(sys.argv) > 1 else "1 D"
    bar_size = sys.argv[2] if len(sys.argv) > 2 else "1 min"

    OUTPUT_DIR.mkdir(exist_ok=True)

    ib_client = IBClient()
    ib_client.connect(config.TWS_HOST, config.TWS_PORT, config.DOWNLOAD_CLIENT_ID)
    threading.Thread(target=run_loop, args=(ib_client,), daemon=True).start()

    if not ib_client.connected_event.wait(timeout=10):
        print("Timed out waiting for TWS connection (nextValidId not received).")
        ib_client.disconnect()
        return

    symbol = config.TARGET_TICKERS[0]
    contract = create_us_stock(symbol)

    ib_client.data_handler.clear()
    ib_client.historical_data_end_event.clear()
    ib_client.reqHistoricalData(
        HISTORICAL_REQ_ID,
        contract,
        "",            # endDateTime: "" means now
        duration_str,
        bar_size,
        "TRADES",
        1,             # useRTH: regular trading hours only
        1,             # formatDate: yyyymmdd HH:mm:ss
        False,         # keepUpToDate: one-shot snapshot
        [],            # chartOptions
    )

    if not ib_client.historical_data_end_event.wait(timeout=120):
        print("Timed out waiting for historical data download.")
        ib_client.disconnect()
        return

    price_dataframe = ib_client.data_handler.get_dataframe()
    sanitized_bar_size = bar_size.replace(" ", "")
    output_path = OUTPUT_DIR / f"{symbol.lower()}_{sanitized_bar_size}.csv"
    price_dataframe.to_csv(output_path)
    print(f"Saved {len(price_dataframe)} bars of {symbol} ({bar_size}) to {output_path}")

    ib_client.disconnect()


if __name__ == "__main__":
    main()
