"""Relational entities for users, sessions, and study progress."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """An owner account for one or more study sessions."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )


class UserSession(TimestampMixin, Base):
    """A user's isolated study and cache session."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class StudyProgress(TimestampMixin, Base):
    """Current chapter position, scoped to a single session."""

    __tablename__ = "study_progresses"
    __table_args__ = (
        CheckConstraint(
            "current_module > 0", name="ck_study_progresses_module_positive"
        ),
        CheckConstraint(
            "current_chapter > 0", name="ck_study_progresses_chapter_positive"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    current_module: Mapped[int] = mapped_column(default=1, nullable=False)
    current_chapter: Mapped[int] = mapped_column(default=1, nullable=False)
