from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security import decode_access_token


def get_rate_limit_key(request: Request) -> str:
    """Authenticated: limit per user. Anonymous: limit per IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            return f"user:{decode_access_token(auth[7:])['sub']}"
        except (JWTError, KeyError):
            pass
    return f"ip:{get_remote_address(request)}"


# Limiter instance — uses Redis as storage so limits persist
# across multiple app instances (important for Kubernetes in Phase 10)
limiter = Limiter(key_func=get_rate_limit_key, storage_uri=settings.RATE_LIMIT_STORAGE_URL)


def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """
    Custom error response when rate limit is hit.
    The Retry-After header tells clients when they can try again
    — this is part of the RFC 6585 standard.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "limit": str(exc.limit),
            "retry_after": "60 seconds",
        },
        headers={"Retry-After": "60"},
    )