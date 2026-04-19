"""Request middleware. Calls into auth."""
from auth import validate_token  # BUG 1: was renamed to verify_token


def require_auth(request):
    token = request.get("token")
    if not validate_token(token):
        raise PermissionError("Auth failed")
    return True
