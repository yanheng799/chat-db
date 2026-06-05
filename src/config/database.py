from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import Settings

_settings = Settings()

_engine = create_async_engine(
    f"postgresql+asyncpg://{_settings.postgres_user}"
    f":{_settings.postgres_password}"
    f"@{_settings.postgres_host}"
    f":{_settings.postgres_port}"
    f"/{_settings.postgres_db}",
    pool_size=5,
    max_overflow=10,
)

_async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _async_session_factory() as session:
        yield session
