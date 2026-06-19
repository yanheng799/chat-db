from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory


@pytest.fixture()
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
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
def embedding_client():
    from knowledge.embedding import EmbeddingClient

    return EmbeddingClient()


@pytest.fixture()
def milvus_store():
    """A real Milvus VectorStore on a throwaway test collection (dropped per test)."""
    from knowledge.vector_store import VectorStore

    store = VectorStore(collection_name="field_descriptions_test")
    store.drop()
    store.ensure_collection()
    yield store
    store.drop()


@pytest.fixture()
def neo4j_store():
    """A real Neo4j GraphStore; dev DB is wiped per test for isolation."""
    from knowledge.graph_store import GraphStore

    store = GraphStore()
    store.wipe_all()
    yield store
    store.wipe_all()
    store.close()
