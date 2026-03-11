"""
Shared FastAPI dependencies.

get_optional_user: resolves a User from a Bearer token, or None if unauthenticated.
Use this on endpoints that work for both logged-in and anonymous users.

Why optional auth instead of required:
  During development, not every curl / Postman test will include a token.
  Making auth optional lets the app remain fully functional for unauthenticated
  dev use while still attaching user identity when a token is present.
  In production, you'd add a required `get_current_user` dependency to
  protect private routes.
"""
import uuid
import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_token
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# auto_error=False means FastAPI won't raise 403 if the Authorization header is
# missing — it passes None to the dependency instead.
_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the authenticated User, or None if no valid token is provided."""
    if credentials is None:
        return None
    try:
        user_id_str = decode_token(credentials.credentials)
        user = await db.get(User, uuid.UUID(user_id_str))
        return user  # None if user was deleted after token was issued
    except (JWTError, ValueError):
        # Invalid token format or expired — treat as unauthenticated
        logger.debug("Invalid or expired token, treating as anonymous")
        return None
