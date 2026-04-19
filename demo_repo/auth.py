"""Handles token validation."""


def verify_token(token: str) -> bool:
    if not token:
        return False
    return token.startswith("valid_")


def hash_password(password: str) -> str:
    return f"hashed_{password}"
