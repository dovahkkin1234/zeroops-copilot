"""Session and request handlers. Calls into auth."""
from auth import validate_token  # BUG 4: stale import — validate_token was renamed to verify_token


def check_session(request):
    session_token = request.get("session_token")
    if not validate_token(session_token):
        raise PermissionError("Session expired")
    return True


def handle_login(credentials):
    token = credentials.get("token")
    if not validate_token(token):
        raise PermissionError("Invalid credentials")
    return {"status": "ok", "token": token}
