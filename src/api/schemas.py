from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    engine: str = Field(..., pattern=r"^(postgresql|mysql)$")
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1, max_length=100)
    schema_whitelist: list[dict] | None = None

    @model_validator(mode="after")
    def validate_engine_value(self) -> DataSourceCreate:
        if self.engine not in ("postgresql", "mysql"):
            raise ValueError("engine must be 'postgresql' or 'mysql'")
        return self


class DataSourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    engine: str | None = None
    host: str | None = Field(None, min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, min_length=1, max_length=100)
    password: str | None = None
    database: str | None = Field(None, min_length=1, max_length=100)
    schema_whitelist: list[dict] | None = None


class DataSourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    engine: str
    host: str
    port: int
    username: str
    database: str
    schema_whitelist: list[dict] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str | None = None


class TableScopeItem(BaseModel):
    schema_name: str = Field(..., alias="schema")
    table: str


class SyncRequest(BaseModel):
    table_scope: list[TableScopeItem] | None = None


class SyncResponse(BaseModel):
    sync_log_id: uuid.UUID
    message: str


class MetadataOverview(BaseModel):
    table_count: int
    column_count: int


class SyncLogResponse(BaseModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    sync_type: str
    scope: list[dict] | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    tables_added: int | None = None
    tables_removed: int | None = None
    columns_changed: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class LearnResponse(BaseModel):
    learning_log_id: uuid.UUID
    message: str


class LearningLogResponse(BaseModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    tables_processed: int | None = None
    columns_described: int | None = None
    l0_count: int | None = None
    l1_count: int | None = None
    l2_count: int | None = None
    l2_llm_calls: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
