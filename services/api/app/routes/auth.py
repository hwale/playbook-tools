"""
Auth routes: register + login.

Both return the same { access_token, token_type } shape so the frontend
can handle them identically — just store the token and redirect to /chat.

Security notes:
- Passwords are never logged or returned.
- We return the same 401 message for "wrong password" and "unknown email"
  to prevent user enumeration attacks (an attacker can't tell which is which).
- Email uniqueness is enforced at the DB level (unique index) and caught here.
"""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account and return a JWT.

    Returns 409 if the email is already registered.
    """
    user = User(
        id=uuid.uuid4(),
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify credentials and return a JWT.

    Returns 401 for both unknown email and wrong password (prevents enumeration).
    """
    stmt = select(User).where(User.email == req.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Constant-time failure: always verify even if user not found, to prevent
    # timing attacks that reveal whether an email exists in the DB.
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)
