import datetime
import pytz
import pandas_market_calendars as mcal

def is_market_open():
    nyse = mcal.get_calendar('NYSE')
    eastern = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(eastern)

    schedule = nyse.schedule(start_date=now.date(), end_date=now.date())
    if schedule.empty:
        return False

    market_open = schedule.iloc[0]['market_open']
    market_close = schedule.iloc[0]['market_close']

    return market_open <= now <= market_close
