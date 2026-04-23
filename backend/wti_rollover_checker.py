from datetime import datetime, timedelta

def get_wti_alert_date(year: int, month: int) -> str:
    """
    Returns the string 'YYYY-MM-DD' of the day we should alert the user
    for the WTI contract rollover that happens in the given month.
    """
    # Major US holidays assuming 2026 for now, but simple to keep up to date
    # In a full prod system, use 'holidays' library
    holidays_2026 = [
        datetime(2026,1,1).date(), datetime(2026,1,19).date(), datetime(2026,2,16).date(),
        datetime(2026,4,3).date(), datetime(2026,5,25).date(), datetime(2026,6,19).date(),
        datetime(2026,7,3).date(), datetime(2026,9,7).date(), datetime(2026,11,26).date(),
        datetime(2026,12,25).date()
    ]

    def is_biz(d):
        return d.weekday() < 5 and d not in holidays_2026

    day25 = datetime(year, month, 25).date()
    days_to_subtract = 3 if is_biz(day25) else 4
    
    # find LTD (Last Trading Day)
    ltd = day25
    while days_to_subtract > 0:
        ltd -= timedelta(days=1)
        if is_biz(ltd):
            days_to_subtract -= 1
            
    # Session starts 2 biz days prior to LTD
    biz_to_subtract = 2
    sess_date = ltd
    while biz_to_subtract > 0:
        sess_date -= timedelta(days=1)
        if is_biz(sess_date):
            biz_to_subtract -= 1
            
    # The actual swap is the calendar day BEFORE the sess_date (since it's 6 PM ET)
    swap_day = sess_date - timedelta(days=1)
    
    # We alert 1 day before swap_day
    alert_day = swap_day - timedelta(days=1)
    return alert_day.strftime('%Y-%m-%d')
