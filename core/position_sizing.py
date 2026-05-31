import math


def calculate_shares(cash_balance: float, price: float, position_pct: float) -> int:
    """Return the whole-share count that deploys `position_pct` of `cash_balance`
    at `price`.

    Returns 0 when any input is non-positive or the budget cannot afford one
    share. Floors to a whole number because stocks trade in integer shares.
    """
    if cash_balance <= 0 or price <= 0 or position_pct <= 0:
        return 0
    budget = cash_balance * position_pct
    return max(0, math.floor(budget / price))
