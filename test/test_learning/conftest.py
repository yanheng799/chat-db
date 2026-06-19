from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app
from config.database import get_session
from config.settings import Settings


@pytest.fixture()
async def engine():
    settings = Settings()
    eng = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}"
        f":{settings.postgres_password}"
        f"@{settings.postgres_host}"
        f":{settings.postgres_port}"
        f"/{settings.postgres_db}",
    )
    yield eng
    await eng.dispose()


@pytest.fixture()
async def session_factory(engine) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Shared async session factory for tests that need independent sessions.

    Code paths that open concurrent sessions (e.g. L2) must receive a factory
    rather than a single shared ``AsyncSession``.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory


@pytest.fixture()
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        # Clean tables in reverse FK order
        from config.data_source_model import DataSource
        from metadata.models import (
            MetadataChangeLog,
            MetadataColumn,
            MetadataForeignKey,
            MetadataIndex,
            MetadataInferredForeignKey,
            MetadataLearningLog,
            MetadataSyncLog,
            MetadataTable,
        )

        await session.execute(MetadataChangeLog.__table__.delete())
        await session.execute(MetadataInferredForeignKey.__table__.delete())
        await session.execute(MetadataForeignKey.__table__.delete())
        await session.execute(MetadataIndex.__table__.delete())
        await session.execute(MetadataColumn.__table__.delete())
        await session.execute(MetadataTable.__table__.delete())
        await session.execute(MetadataSyncLog.__table__.delete())
        await session.execute(MetadataLearningLog.__table__.delete())
        await session.execute(DataSource.__table__.delete())
        await session.commit()
        yield session


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
