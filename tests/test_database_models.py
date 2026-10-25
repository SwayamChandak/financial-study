"""Integration tests for relational ownership and progress persistence."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from infrastructure.database.base import Base
from infrastructure.database.connection import create_session_factory
from infrastructure.database.models import StudyProgress, User, UserSession


@pytest.mark.asyncio
async def test_session_owns_fresh_progress_record() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        user = User()
        session.add(user)
        await session.flush()

        owner_session = UserSession(user_id=user.id)
        session.add(owner_session)
        await session.flush()

        progress = StudyProgress(session_id=owner_session.id)
        session.add(progress)
        await session.commit()

        stored_progress = await session.scalar(
            select(StudyProgress).where(StudyProgress.session_id == owner_session.id)
        )

    await engine.dispose()

    assert isinstance(user.id, UUID)
    assert stored_progress is not None
    assert stored_progress.current_module == 1
    assert stored_progress.current_chapter == 1
