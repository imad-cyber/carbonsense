from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from app.db.database import get_db
from app.schemas.user import UserCreate, UserResponse, TokenResponse, LoginRequest
from app.services.user_service import UserService
from app.core.security import create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.core.rate_limiter import limiter
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
# 10 registrations per minute per IP — prevents automated account creation
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    return UserService.create(db, payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
# 5 login attempts per minute — core brute-force protection
# Combined with bcrypt's slowness, this makes password attacks impractical
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = UserService.authenticate(db, payload.email, payload.password)
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    token = create_access_token(
        subject=user.email,
        role=user.role,
        expires_delta=timedelta(minutes=expire_minutes),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
        user=user,
    )


@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
def get_me(request: Request, current_user: User = Depends(get_current_active_user)):
    return current_user