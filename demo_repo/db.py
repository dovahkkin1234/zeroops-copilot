"""Database layer. Calls into utils."""
from utils import normalize_string  # BUG 2: was renamed to normalize_text


def insert_record(table, data):
    clean_data = {k: normalize_string(v) for k, v in data.items()}
    return {"status": "ok", "table": table}
