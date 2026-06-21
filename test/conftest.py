import os
import sys
import warnings

import pytest

from config.encryption import generate_fernet_key

# Production database that tests must NEVER touch.
_PROD_DB = "chat_db"
# Safe test database — created automatically.
_TEST_DB = "chat_db_test"


def pytest_configure(config: pytest.Config) -> None:
    """Force tests to run against a dedicated test database.

    Tests truncate DataSource / metadata tables on every session, so
    accidentally running against the production database would destroy real
    data. Instead of refusing outright, this hook transparently redirects
    POSTGRES_DB to ``chat_db_test`` when it points to ``chat_db``.

    If you need a different test database name, set
    ``POSTGRES_DB=my_test_db`` in ``.env`` (any name containing ``test``
    passes the safety check).
    """
    from config.settings import Settings

    settings = Settings()
    db = settings.postgres_db.lower()
    if "test" not in db:
        if db == _PROD_DB:
            os.environ["POSTGRES_DB"] = _TEST_DB
            warnings.warn(
                f"SAFETY: POSTGRES_DB={settings.postgres_db!r} → overridden to "
                f"{_TEST_DB!r} for tests. Real data sources in {_PROD_DB!r} "
                f"are untouched.",
                stacklevel=2,
            )
        else:
            sys.exit(
                f"\n  SAFETY BLOCK: POSTGRES_DB={settings.postgres_db!r} — "
                f"database name must contain 'test' to run tests.\n"
                f"  Tests truncate DataSource / metadata tables. "
                f"Set POSTGRES_DB=chat_db_test in .env or create a separate test database.\n"
            )


@pytest.fixture()
def fernet_key() -> str:
    return generate_fernet_key()


@pytest.fixture(scope="session", autouse=True)
async def _ensure_value_tables() -> None:
    """Create mapping tables that aren't managed by ORM Base.metadata.

    ``value_enum_mappings``, ``value_region_dict``, and
    ``value_name_mappings`` are accessed via raw SQL in
    ``normalizer/mapping_service.py`` — they have no ORM model class, so
    ``Base.metadata.create_all`` doesn't create them. Without this fixture,
    any test that calls upsert_enum_alias / upsert_region / upsert_name_mapping
    on a fresh test database will fail with ``UndefinedTableError``.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from config.settings import Settings

    settings = Settings()
    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS value_enum_mappings (
                id UUID PRIMARY KEY,
                data_source_id UUID NOT NULL,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                value TEXT NOT NULL,
                display TEXT,
                aliases JSONB DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT now(),
                UNIQUE (data_source_id, table_name, column_name, value)
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS value_region_dict (
                id UUID PRIMARY KEY,
                data_source_id UUID NOT NULL,
                code TEXT NOT NULL,
                parent_code TEXT,
                level TEXT,
                name TEXT,
                aliases JSONB DEFAULT '[]'
            )
        """))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS value_name_mappings (
                id UUID PRIMARY KEY,
                data_source_id UUID NOT NULL,
                short_name TEXT NOT NULL,
                full_name TEXT,
                target_table TEXT,
                aliases JSONB DEFAULT '[]',
                UNIQUE (data_source_id, short_name)
            )
        """))
        await session.commit()
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engines() -> None:
    """Dispose async engines at end of test session so asyncpg connections
    terminate cleanly while the event loop is still alive.

    Without this, SQLAlchemy tears its pool down during garbage collection
    (against a shutting-down loop), which prints noisy ``CancelledError``
    and ``SAWarning`` stack traces to stderr.
    """
    yield
    from config.database import dispose_engine

    await dispose_engine()
