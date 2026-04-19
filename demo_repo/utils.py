"""Utility helpers."""


def normalize_text(s: str) -> str:
    return s.strip().lower()


def parse_date(s: str):
    """Returns None for invalid input. Callers must check."""
    try:
        return [int(x) for x in s.split("-")]
    except Exception:
        return None
