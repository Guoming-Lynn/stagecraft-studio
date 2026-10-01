"""SQLAlchemy base. Schema changes go through Alembic revisions."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata for the eight core tables."""
