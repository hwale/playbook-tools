import uuid

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Unique email — used as the login identifier.
    # Index created in migration for fast lookup by email.
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # bcrypt hash of the password. We never store or log the plaintext.
    # passlib's CryptContext handles the hash format and work factor automatically.
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
