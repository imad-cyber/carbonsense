from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """
    RBAC roles for CarbonSense.
    Each role maps to different permissions:

    admin    → full access, can manage users and companies
    analyst  → can read/write emission data, cannot manage users
    auditor  → read-only access to all data (for CSRD verification)
    supplier → can only submit their own emission records
    """
    ADMIN = "admin"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    SUPPLIER = "supplier"


class UserCreate(BaseModel):
    email: EmailStr  # Pydantic validates email format automatically
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    role: UserRole = UserRole.ANALYST

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Basic password policy — production systems often use
        zxcvbn (a proper strength estimator) but this is a good start.
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    The response from POST /auth/login.
    access_token is the JWT the client stores and sends with every request.
    token_type is always "bearer" — this is the OAuth2 standard.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
    user: UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str