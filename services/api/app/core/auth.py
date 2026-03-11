"""
JWT + password hashing utilities.

Mental model for interviews:
- Passwords: bcrypt is a one-way hash. You can verify a guess but can't reverse
  the hash. Work factor (12 rounds) makes brute-force infeasible.
- JWTs: a signed JSON payload. The server signs it with SECRET_KEY. Anyone can
  decode the payload but can't forge a valid signature without the key.
  Stateless — no DB lookup needed to authenticate, just signature verification.
  Trade-off: tokens can't be revoked until they expire (use short expiry + refresh
  tokens for sensitive apps; 1-week tokens are fine for a learning project).
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
# 7-day expiry — long enough for dev comfort, short enough to limit exposure.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    """
    Create a signed JWT for the given user.

    Payload:
      sub (subject): user UUID as string
      exp (expiry):  timestamp when the token becomes invalid
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """
    Decode and verify a JWT. Returns the user_id (sub claim) as a string.
    Raises jose.JWTError if the token is invalid or expired.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token missing sub claim")
    return user_id
