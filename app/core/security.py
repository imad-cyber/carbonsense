from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt  # Replaced passlib with native bcrypt
from jose import JWTError, jwt
from app.core.config import settings


def hash_password(plain_password: str) -> str:
    """
    Converts a plain password into a bcrypt hash string.
    
    We convert the input string to bytes, generate a fresh salt,
    hash it, and decode the final byte-hash back into a standard string
    so it can be stored easily in the database.
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored hash string.
    
    Both strings are converted to bytes. bcrypt extracts the salt 
    automatically from the hashed_password bytes to perform the check.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        # Gracefully handles malformed hashes, empty inputs, or type errors
        return False


def create_access_token(
    subject: str | Any,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Creates a signed JWT token.

    The payload (called 'claims') contains:
    - sub: the subject — conventionally the user's email or id
    - role: used for RBAC checks in route dependencies
    - exp: expiry timestamp — jose validates this automatically
    - iat: issued-at timestamp — useful for audit logs

    The token is signed with SECRET_KEY using the HS256 algorithm.
    Anyone can decode the payload (it's just base64), but they cannot
    FORGE a token without the SECRET_KEY. Never put sensitive data in tokens.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    payload = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.
    Raises JWTError if:
    - Signature is invalid (token was tampered with)
    - Token has expired
    - Token is malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        raise  # caller handles this
