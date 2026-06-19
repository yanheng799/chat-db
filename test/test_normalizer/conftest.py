from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import Settings


@pytest.fixture()
async def engine():
    settings = Settings()
    eng = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    yield eng
    await eng.dispose()


@pytest.fixture()
async def session_factory(engine) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory


@pytest.fixture()
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        from config.data_source_model import DataSource
        from metadata.models import (MetadataChangeLog, MetadataColumn, MetadataForeignKey, MetadataIndex, MetadataInferredForeignKey, MetadataLearningLog, MetadataSyncLog, MetadataTable)
        for T in (MetadataChangeLog, MetadataInferredForeignKey, MetadataForeignKey, MetadataIndex, MetadataColumn, MetadataTable, MetadataSyncLog, MetadataLearningLog, DataSource):
            await session.execute(T.__table__.delete())
        await session.commit()
        yield session
