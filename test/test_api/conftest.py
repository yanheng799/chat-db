from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app
from config.database import get_session
from config.models import Base
from config.settings import Settings


@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = Settings()
    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}"
        f":{settings.postgres_password}"
        f"@{settings.postgres_host}"
        f":{settings.postgres_port}"
        f"/{settings.postgres_db}",
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        # Clean tables in reverse FK order
        from metadata.models import MetadataChangeLog, MetadataForeignKey, MetadataIndex, MetadataColumn, MetadataTable, MetadataSyncLog
        from config.data_source_model import DataSource

        await session.execute(MetadataChangeLog.__table__.delete())
        await session.execute(MetadataForeignKey.__table__.delete())
        await session.execute(MetadataIndex.__table__.delete())
        await session.execute(MetadataColumn.__table__.delete())
        await session.execute(MetadataTable.__table__.delete())
        await session.execute(MetadataSyncLog.__table__.delete())
        await session.execute(DataSource.__table__.delete())
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
