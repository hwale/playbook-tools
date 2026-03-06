# Import all models here so Alembic can discover them when generating migrations.
# If a model isn't imported, Alembic won't know it exists and won't create its table.
from app.models.base import Base
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage

__all__ = ["Base", "Document", "ChatSession", "ChatMessage"]
