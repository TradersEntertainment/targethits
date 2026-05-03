"""
WTI Crude Oil Active Contract Resolver

Determines which WTI futures contract is the "Active Month" per CME/Polymarket rules:
- LTD = 3 business days before 25th of month preceding delivery month
        (4 business days if the 25th is not a business day)
- Active month switches at the START of the 2nd trading session prior to LTD session
- A trading session for business day X starts at 6 PM ET on the prior calendar day
"""

from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

# CME futures month codes
MONTH_CODES = {
    1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
    7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
}

# US market holidays (CME observed) for 2026-2027
# Keep this updated annually or switch to `holidays` library in production
US_MARKET_HOLIDAYS = {
    # 2026
    datetime(2026, 1, 1).date(),   # New Year's Day
    datetime(2026, 1, 19).date(),  # MLK Day
    datetime(2026, 2, 16).date(),  # Presidents Day
    datetime(2026, 4, 3).date(),   # Good Friday
    datetime(2026, 5, 25).date(),  # Memorial Day
    datetime(2026, 6, 19).date(),  # Juneteenth
    datetime(2026, 7, 3).date(),   # Independence Day (observed)
    datetime(2026, 9, 7).date(),   # Labor Day
    datetime(2026, 11, 26).date(), # Thanksgiving
    datetime(2026, 12, 25).date(), # Christmas
    # 2027
    datetime(2027, 1, 1).date(),
    datetime(2027, 1, 18).date(),
    datetime(2027, 2, 15).date(),
    datetime(2027, 3, 26).date(),  # Good Friday
    datetime(2027, 5, 31).date(),  # Memorial Day
    datetime(2027, 7, 5).date(),   # Independence Day (observed, Jul 4 is Sun)
    datetime(2027, 9, 6).date(),   # Labor Day
    datetime(2027, 11, 25).date(), # Thanksgiving
    datetime(2027, 12, 24).date(), # Christmas (observed, Dec 25 is Sat)
}


def _is_business_day(d):
    """Check if a date is a business day (weekday + not a holiday)."""
    return d.weekday() < 5 and d not in US_MARKET_HOLIDAYS


def _prev_business_day(d):
    """Get the previous business day before date d."""
    d = d - timedelta(days=1)
    while not _is_business_day(d):
        d -= timedelta(days=1)
    return d


def _count_back_business_days(d, n):
    """Count back n business days from d (not including d itself)."""
    result = d
    for _ in range(n):
        result = _prev_business_day(result)
    return result


def get_ltd(delivery_year: int, delivery_month: int):
    """
    Calculate the Last Trading Day for a WTI CL contract.

    Per CME specs: LTD = 3 business days prior to the 25th of the month
    preceding the contract's delivery month. If the 25th is not a business
    day, use 4 business days prior.
    """
    # Month preceding delivery month
    if delivery_month == 1:
        prec_month, prec_year = 12, delivery_year - 1
    else:
        prec_month, prec_year = delivery_month - 1, delivery_year

    day25 = datetime(prec_year, prec_month, 25).date()
    n = 3 if _is_business_day(day25) else 4
    return _count_back_business_days(day25, n)


def get_rollover_datetime_utc(delivery_year: int, delivery_month: int):
    """
    Calculate when the active month switches AWAY from this contract (UTC).

    The switch happens at the start of the 2nd trading session prior to the
    LTD session. A session for business day X starts at 6 PM ET on the
    prior calendar day.

    Returns a timezone-aware UTC datetime.
    """
    ltd = get_ltd(delivery_year, delivery_month)

    # Find the 2nd business day before LTD
    one_prior = _prev_business_day(ltd)
    two_prior = _prev_business_day(one_prior)

    # Session for two_prior starts at 6 PM ET on (two_prior - 1 calendar day)
    session_start_date = two_prior - timedelta(days=1)

    # 6 PM ET = 22:00 UTC (EST) or 22:00 UTC (EDT depends on DST)
    # For simplicity and safety, use 22:00 UTC (covers EST; EDT would be 22:00 UTC = 6PM EDT)
    # Actually: ET in summer (EDT) = UTC-4, so 6PM EDT = 22:00 UTC
    # ET in winter (EST) = UTC-5, so 6PM EST = 23:00 UTC
    # Most WTI rollovers happen in months where EDT is active (Mar-Nov)
    # We'll use a simple heuristic: if month is in [3..10], use EDT (UTC-4), else EST (UTC-5)
    month = session_start_date.month
    utc_offset_hours = 4 if 3 <= month <= 10 else 5

    rollover_utc = datetime(
        session_start_date.year,
        session_start_date.month,
        session_start_date.day,
        18 + utc_offset_hours, 0, 0,
        tzinfo=timezone.utc
    )
    return rollover_utc


def get_active_wti_symbol(now_utc=None):
    """
    Returns the Pyth symbol for the currently active WTI contract.

    E.g. 'Commodities.WTIN6/USD' for July 2026.

    Args:
        now_utc: Current time as timezone-aware UTC datetime.
                 If None, uses datetime.now(timezone.utc).

    Returns:
        tuple: (pyth_symbol, delivery_month, delivery_year)
               e.g. ('Commodities.WTIN6/USD', 7, 2026)
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Check contracts starting from next month, up to 3 months ahead
    for offset in range(1, 4):
        total = now_utc.month + offset
        delivery_year = now_utc.year + (total - 1) // 12
        delivery_month = (total - 1) % 12 + 1

        rollover_dt = get_rollover_datetime_utc(delivery_year, delivery_month)

        if now_utc < rollover_dt:
            month_code = MONTH_CODES[delivery_month]
            year_digit = str(delivery_year % 10)
            symbol = f"Commodities.WTI{month_code}{year_digit}/USD"
            logger.info(
                f"Active WTI contract: {symbol} "
                f"(delivery {delivery_year}-{delivery_month:02d}, "
                f"rollover at {rollover_dt.isoformat()})"
            )
            return symbol, delivery_month, delivery_year

    # Fallback: should never reach here
    logger.error("Could not determine active WTI contract!")
    return None, None, None


def get_next_rollover_info(now_utc=None):
    """
    Returns info about the next upcoming rollover.

    Returns:
        dict with keys: rollover_utc, current_symbol, next_symbol
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    current_symbol, del_month, del_year = get_active_wti_symbol(now_utc)
    if not current_symbol:
        return None

    rollover_dt = get_rollover_datetime_utc(del_year, del_month)

    # Next contract
    next_month = del_month + 1
    next_year = del_year
    if next_month > 12:
        next_month = 1
        next_year += 1
    next_code = MONTH_CODES[next_month]
    next_year_digit = str(next_year % 10)
    next_symbol = f"Commodities.WTI{next_code}{next_year_digit}/USD"

    return {
        "rollover_utc": rollover_dt,
        "current_symbol": current_symbol,
        "next_symbol": next_symbol,
        "current_delivery_month": del_month,
        "current_delivery_year": del_year,
    }
