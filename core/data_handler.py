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
        row = {
            "time": getattr(bar, "date", None),
            "Open": bar.open,
            "High": bar.high,
            "Low": bar.low,
            "Close": bar.close,
            "Volume": bar.volume,
        }
        with self._lock:
            self._bars.append(row)

    def get_dataframe(self) -> pd.DataFrame:
        """Return a DataFrame indexed by datetime with numeric OHLCV columns."""
        with self._lock:
            rows = list(self._bars)

        if not rows:
            return pd.DataFrame(columns=self.OHLCV_COLUMNS).rename_axis("time")

        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=False)
        df = df.set_index("time").sort_index()

        for col in self.OHLCV_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df[self.OHLCV_COLUMNS]

    def clear(self) -> None:
        with self._lock:
            self._bars.clear()
