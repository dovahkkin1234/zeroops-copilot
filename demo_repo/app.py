"""Main app. Has an unchecked None from parse_date."""
from utils import parse_date


def get_events_on(date_str):
    parts = parse_date(date_str)
    year, month, day = parts  # BUG 3: parts can be None; TypeError
    return {"year": year}
