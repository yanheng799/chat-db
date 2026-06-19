import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.models import Base


class MetadataTable(Base):
    __tablename__ = "metadata_tables"
    __table_args__ = (
        UniqueConstraint("data_source_id", "schema_name", "table_name", name="uq_metadata_tables_ds_schema_table"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    table_type: Mapped[str] = mapped_column(String(20), nullable=False, default="BASE TABLE")
    table_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # Learning fields
    semantic_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    columns_rel: Mapped[list["MetadataColumn"]] = relationship(
        "MetadataColumn", back_populates="table", cascade="all, delete-orphan"
    )
    indexes_rel: Mapped[list["MetadataIndex"]] = relationship(
        "MetadataIndex", back_populates="table", cascade="all, delete-orphan"
    )
    foreign_keys_rel: Mapped[list["MetadataForeignKey"]] = relationship(
        "MetadataForeignKey", back_populates="table", cascade="all, delete-orphan"
    )


class MetadataColumn(Base):
    __tablename__ = "metadata_columns"
    __table_args__ = (UniqueConstraint("table_id", "column_name", name="uq_metadata_columns_table_column"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Learning fields
    semantic_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_enum_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    null_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    numeric_range: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    table: Mapped["MetadataTable"] = relationship("MetadataTable", back_populates="columns_rel")


class MetadataIndex(Base):
    __tablename__ = "metadata_indexes"
    __table_args__ = (UniqueConstraint("table_id", "index_name", name="uq_metadata_indexes_table_index"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False)
    index_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_names: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False)

    table: Mapped["MetadataTable"] = relationship("MetadataTable", back_populates="indexes_rel")


class MetadataForeignKey(Base):
    __tablename__ = "metadata_foreign_keys"
    __table_args__ = (UniqueConstraint("table_id", "constraint_name", name="uq_metadata_fks_table_constraint"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata_tables.id", ondelete="CASCADE"), nullable=False)
    constraint_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_schema: Mapped[str] = mapped_column(String(100), nullable=False)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    target_column: Mapped[str] = mapped_column(String(100), nullable=True)

    table: Mapped["MetadataTable"] = relationship("MetadataTable", back_populates="foreign_keys_rel")


class MetadataInferredForeignKey(Base):
    """A foreign-key relationship inferred from value overlap (Phase 2 L1).

    Separate from :class:`MetadataForeignKey` (which stores explicitly declared
    FKs) so downstream consumers can distinguish declared vs inferred relations,
    mirroring the graph layer's ``REFERENCES`` vs ``INFERRED_REF`` edges.
    Recomputed and replaced on every learning run.
    """

    __tablename__ = "metadata_inferred_fks"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id",
            "source_table",
            "source_column",
            "target_table",
            "target_column",
            name="uq_metadata_inferred_fks_pair",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    source_schema: Mapped[str] = mapped_column(String(100), nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_column: Mapped[str] = mapped_column(String(100), nullable=False)
    target_schema: Mapped[str] = mapped_column(String(100), nullable=False)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    target_column: Mapped[str] = mapped_column(String(100), nullable=False)
    overlap_rate: Mapped[float] = mapped_column(Float, nullable=False)
    name_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class MetadataSyncLog(Base):
    __tablename__ = "metadata_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    sync_type: Mapped[str] = mapped_column(
        Enum("full", "manual", name="enum_sync_type"),
        nullable=False,
    )
    scope: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("running", "success", "failed", name="enum_sync_status"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tables_added: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tables_removed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    columns_changed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetadataChangeLog(Base):
    __tablename__ = "metadata_change_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sync_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metadata_sync_logs.id", ondelete="CASCADE"), nullable=False
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    change_type: Mapped[str] = mapped_column(
        Enum(
            "table_added",
            "table_removed",
            "column_added",
            "column_removed",
            "column_modified",
            "index_added",
            "index_removed",
            "fk_added",
            "fk_removed",
            name="enum_change_type",
        ),
        nullable=False,
    )
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    object_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MetadataLearningLog(Base):
    __tablename__ = "metadata_learning_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        Enum("auto", "manual", name="enum_learning_trigger_type"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("running", "success", "partial_success", "failed", "aborted", name="enum_learning_status"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tables_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    columns_described: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l0_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l1_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l2_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l2_llm_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
