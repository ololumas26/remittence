from datetime import datetime, date
from src.constant.app_constant import MAJOR_AGE
from calendar import isleap

def get_current_date():
    return datetime.now().date()


def get_18_year_date(birth_date: date) -> date:

    target_year = birth_date.year + MAJOR_AGE

    if birth_date.month == 2 and birth_date.day == 29 and not isleap(target_year):
        return date(target_year, 3, 1)

    return date(year=target_year, month=birth_date.month, day=birth_date.day)
