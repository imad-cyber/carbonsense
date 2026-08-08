from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse


def get_rate_limit_key(request: Request) -> str:
    """
    Key function determines what gets rate limited together.
    Default: by IP address — all requests from the same IP share a quota.

    In Phase 4 we added auth — a better approach is:
    - Authenticated users: rate limit by user ID (higher quota)
    - Unauthenticated: rate limit by IP (lower quota)
    """
    # Try to extract user from JWT for per-user limiting
    # Falls back to IP if not authenticated
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Use the token itself as the key (hashed implicitly by Redis)
        # In production you'd decode it to get the user ID
        return f"user:{auth_header[7:50]}"  # first 50 chars of token
    return f"ip:{get_remote_address(request)}"


# Limiter instance — uses Redis as storage so limits persist
# across multiple app instances (important for Kubernetes in Phase 10)
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri="redis://localhost:6379/3",
    # /3 is a separate Redis DB so rate limit data
    # doesn't mix with our cache data
)


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