from dataclasses import dataclass


@dataclass
class PositionState:
    """In-flight long position. Shared by the backtester and the live loop.

    The backtester ticks bars_held once per simulated bar; the live loop ticks
    it once per completed real-time bar (not on every mid-bar update from TWS).
    """

    shares: int
    entry_price: float
    highest_price_since_entry: float
    bars_held: int = 0

    def tick(self) -> None:
        """Advance the bar counter by one. Call once per completed bar."""
        self.bars_held += 1

    def update_trailing_high(self, current_price: float) -> None:
        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price

    def realized_pnl_at(self, exit_price: float) -> float:
        return (exit_price - self.entry_price) * self.shares


def check_risk_stops(
    position_state: PositionState,
    current_price: float,
    trailing_stop_pct: float,
    max_hold_bars: int,
) -> str | None:
    """Return the stop reason that fires this bar, or None.

    Pure decision function — does not mutate state, does no I/O.

    Trailing stop is checked before time stop so a sharp drop on the final
    allowed bar still logs as 'TRAILING_STOP'.
    """
    trailing_floor = position_state.highest_price_since_entry * (1 - trailing_stop_pct)
    if current_price <= trailing_floor:
        return "TRAILING_STOP"
    if position_state.bars_held >= max_hold_bars:
        return "TIME_STOP"
    return None
