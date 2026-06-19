"""Milvus ``field_descriptions`` vector store.

Indexes the semantic description of each *covered* column (``semantic_description
IS NOT NULL``) so downstream semantic matching can do nearest-neighbour retrieval.

- Embed text: ``"{table}.{column}：{semantic_description}"`` (table/column context
  disambiguates same-named columns across tables).
- Incremental upsert keyed by ``column_id`` (scheme A: compare the embedded text
  against what is already stored; only re-embed changed/new columns).
- All records carry ``data_source_id`` so retrieval and cleanup are scoped per
  data source.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from knowledge.embedding import EmbeddingClient
from metadata.models import MetadataColumn, MetadataTable

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "field_descriptions"


def build_field_text(table_name: str, column_name: str, semantic_description: str) -> str:
    """Build the text that gets embedded for one field."""
    return f"{table_name}.{column_name}：{semantic_description}"


def compute_upsert_plan(
    items: list[dict[str, Any]],
    existing: dict[str, str],
) -> list[dict[str, Any]]:
    """Return items whose embedded text differs from what is already stored.

    ``items``: ``[{column_id, embed_text, ...}]``.
    ``existing``: ``{column_id: stored_embed_text}`` from Milvus.
    An item is included when it is new (column_id absent) or its text changed.
    """
    return [it for it in items if existing.get(it["column_id"]) != it["embed_text"]]


class VectorStore:
    """Thin wrapper over a Milvus collection for field-description vectors."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        collection_name: str = DEFAULT_COLLECTION,
        client: Any = None,
    ) -> None:
        self._settings = settings or Settings()
        self.collection = collection_name
        self._dim = self._settings.embedding_dimension
        if client is not None:
            self._client = client
        else:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=f"http://{self._settings.milvus_host}:{self._settings.milvus_port}")

    def drop(self) -> None:
        if self._client.has_collection(self.collection):
            self._client.drop_collection(self.collection)

    def ensure_collection(self) -> None:
        """Create the collection (cosine + HNSW) if it does not exist, then load."""
        from pymilvus import DataType

        if self._client.has_collection(self.collection):
            self._client.load_collection(self.collection)
            return

        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("column_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("data_source_id", DataType.VARCHAR, max_length=64)
        schema.add_field("table_name", DataType.VARCHAR, max_length=100)
        schema.add_field("column_name", DataType.VARCHAR, max_length=100)
        schema.add_field("description_text", DataType.VARCHAR, max_length=500)
        schema.add_field("description_source", DataType.VARCHAR, max_length=30)
        schema.add_field("description_confidence", DataType.FLOAT)
        self._client.create_collection(self.collection, schema=schema)

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        self._client.create_index(self.collection, index_params=index_params)
        self._client.load_collection(self.collection)

    def upsert(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self._client.upsert(self.collection, records)

    def list_embed_texts(self, data_source_id: str) -> dict[str, str]:
        """Return ``{column_id: stored_embed_text}`` for a data source (for incremental diff)."""
        rows = self._client.query(
            self.collection,
            filter=f'data_source_id == "{data_source_id}"',
            output_fields=["column_id", "description_text"],
            consistency_level="Strong",
        )
        return {r["column_id"]: r["description_text"] for r in rows}

    def search(
        self,
        query_vector: list[float],
        data_source_id: str,
        *,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        res = self._client.search(
            self.collection,
            data=[query_vector],
            anns_field="vector",
            filter=f'data_source_id == "{data_source_id}"',
            limit=top_k,
            consistency_level="Strong",
            output_fields=[
                "column_id",
                "data_source_id",
                "table_name",
                "column_name",
                "description_source",
                "description_confidence",
            ],
        )
        hits = res[0] if res else []
        out: list[dict[str, Any]] = []
        for hit in hits:
            entity = hit.get("entity", {})
            out.append(
                {
                    "column_id": entity.get("column_id"),
                    "data_source_id": entity.get("data_source_id"),
                    "table": entity.get("table_name"),
                    "column": entity.get("column_name"),
                    "description_source": entity.get("description_source"),
                    "description_confidence": entity.get("description_confidence"),
                    "score": hit.get("distance"),
                }
            )
        return out

    def delete_by_data_source(self, data_source_id: str) -> None:
        self._client.delete(self.collection, filter=f'data_source_id == "{data_source_id}"')


async def collect_covered_fields(
    session: AsyncSession,
    data_source_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Read covered columns (with their table) and build embed-text items."""
    result = await session.execute(
        select(MetadataColumn, MetadataTable)
        .join(MetadataTable, MetadataColumn.table_id == MetadataTable.id)
        .where(MetadataTable.data_source_id == data_source_id)
        .where(MetadataColumn.semantic_description.is_not(None))
    )
    items: list[dict[str, Any]] = []
    for col, table in result.all():
        embed_text = build_field_text(table.table_name, col.column_name, col.semantic_description)
        items.append(
            {
                "column_id": str(col.id),
                "embed_text": embed_text,
                "data_source_id": str(data_source_id),
                "table_name": table.table_name,
                "column_name": col.column_name,
                "description_source": col.description_source or "",
                "description_confidence": float(col.description_confidence or 0.0),
            }
        )
    return items


def _to_records(items: list[dict[str, Any]], vectors: list[list[float]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item, vec in zip(items, vectors, strict=True):
        records.append(
            {
                "column_id": item["column_id"],
                "vector": vec,
                "data_source_id": item["data_source_id"],
                "table_name": item["table_name"],
                "column_name": item["column_name"],
                "description_text": item["embed_text"],
                "description_source": item["description_source"],
                "description_confidence": item["description_confidence"],
            }
        )
    return records


async def build_field_vectors(
    session: AsyncSession,
    data_source_id: uuid.UUID,
    *,
    embedding_client: EmbeddingClient,
    vector_store: VectorStore,
) -> int:
    """Incrementally upsert field vectors for a data source.

    Returns the number of columns (re-)embedded and upserted.
    """
    vector_store.ensure_collection()
    items = await collect_covered_fields(session, data_source_id)
    existing = vector_store.list_embed_texts(str(data_source_id))
    plan = compute_upsert_plan(items, existing)
    if not plan:
        return 0
    vectors = embedding_client.embed_sync([it["embed_text"] for it in plan])
    vector_store.upsert(_to_records(plan, vectors))
    return len(plan)


async def search_fields(
    query: str,
    data_source_id: uuid.UUID,
    *,
    embedding_client: EmbeddingClient,
    vector_store: VectorStore,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Nearest-neighbour search for a natural-language query, scoped to a data source."""
    vector_store.ensure_collection()
    query_vector = embedding_client.embed_sync([query])[0]
    return vector_store.search(query_vector, str(data_source_id), top_k=top_k)
