"""Authentication middleware for protecting endpoints."""

from functools import wraps


from app.api.user import get_current_user


def require_auth(f):
    """Decorator that requires a valid Bearer token in the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return {"error": "Authentication required"}, 401
        return f(*args, **kwargs)
    return decorated
