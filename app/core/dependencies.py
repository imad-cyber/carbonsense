from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.user_service import UserService

# HTTPBearer extracts the token from the Authorization header.
# It looks for: "Authorization: Bearer <token>"
# auto_error=False means we handle missing tokens ourselves
# with clearer error messages.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Core auth dependency — every protected route uses this.
    Extracts the JWT, validates it, fetches the user from DB.

    Using Depends() chains dependencies automatically.
    FastAPI resolves the full dependency tree before calling your route.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — provide a Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_email: str = payload.get("sub")
        if not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token — missing subject",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserService.get_by_email(db, user_email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias — confirms user is active. Routes use this as their base dependency."""
    return current_user


class RoleChecker:
    """
    RBAC dependency — created with a list of allowed roles.
    Usage in a route:
        Depends(RoleChecker(["admin", "analyst"]))

    This is the 'callable class' pattern — the instance IS the dependency.
    __call__ is invoked by FastAPI's dependency injection system.
    """
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role}' does not have permission. "
                    f"Required: {self.allowed_roles}"
                ),
            )
        return current_user


# Pre-built role checkers — import and use directly in route definitions
require_admin = RoleChecker(["admin"])
require_analyst_or_above = RoleChecker(["admin", "analyst"])
require_any_authenticated = RoleChecker(["admin", "analyst", "auditor", "supplier"])