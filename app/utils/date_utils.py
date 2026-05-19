from datetime import date, timedelta
from typing import Optional


def get_today() -> date:
    return date.today()


def get_n_days_ago(n: int, from_date: Optional[date] = None) -> date:
    d = from_date or date.today()
    return d - timedelta(days=n)


def format_date_krx(d: date) -> str:
    return d.strftime("%Y%m%d")


def format_date_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def get_start_date(days: int, end_date: Optional[date] = None) -> date:
    end = end_date or date.today()
    # Add buffer for weekends and holidays
    return end - timedelta(days=days + 40)
