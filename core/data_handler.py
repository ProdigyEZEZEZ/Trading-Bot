import threading

import pandas as pd


class DataHandler:
    """Collects raw IB bars on the API thread; exposes them as a DataFrame.

    A lock guards the buffer so the strategy thread can read while the API
    thread is still appending callbacks.
    """

    OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self):
        self._bars: list[dict] = []
        self._lock = threading.Lock()

    def add_bar(self, bar) -> None:
        """Append a raw ibapi BarData (or real-time bar) to the buffer."""
        bar_row = self._build_row(bar)
        with self._lock:
            self._bars.append(bar_row)

    def add_or_update_bar(self, bar) -> None:
        """Live-bar variant: replace the last row when the timestamp matches,
        otherwise append. Use with historicalDataUpdate (keepUpToDate=True)."""
        bar_row = self._build_row(bar)
        with self._lock:
            if self._bars and self._bars[-1]["time"] == bar_row["time"]:
                self._bars[-1] = bar_row
            else:
                self._bars.append(bar_row)

    @staticmethod
    def _build_row(bar) -> dict:
        return {
            "time": getattr(bar, "date", None),
            "Open": bar.open,
            "High": bar.high,
            "Low": bar.low,
            "Close": bar.close,
            "Volume": bar.volume,
        }

    def get_dataframe(self) -> pd.DataFrame:
        """Return a DataFrame indexed by datetime with numeric OHLCV columns."""
        with self._lock:
            bar_rows = list(self._bars)

        if not bar_rows:
            return pd.DataFrame(columns=self.OHLCV_COLUMNS).rename_axis("time")

        price_dataframe = pd.DataFrame(bar_rows)
        price_dataframe["time"] = pd.to_datetime(price_dataframe["time"], errors="coerce", utc=False)
        price_dataframe = price_dataframe.set_index("time").sort_index()

        for column_name in self.OHLCV_COLUMNS:
            price_dataframe[column_name] = pd.to_numeric(price_dataframe[column_name], errors="coerce")

        return price_dataframe[self.OHLCV_COLUMNS]

    def clear(self) -> None:
        with self._lock:
            self._bars.clear()
