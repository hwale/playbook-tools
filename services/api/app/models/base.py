from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared base class for all SQLAlchemy models.

    Every model inherits from this. Alembic uses it to discover all tables —
    it inspects Base.metadata (which collects every subclass) to know what
    the schema should look like, then diffs that against the live database
    to generate migrations automatically.
    """
    pass
