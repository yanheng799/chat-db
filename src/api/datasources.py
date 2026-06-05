from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    ConnectionTestResponse,
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
)
from config.data_source_model import DataSource
from config.database import get_session
from config.encryption import decrypt_value, encrypt_value
from config.settings import Settings

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _model_to_response(ds: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        engine=ds.engine,
        host=ds.host,
        port=ds.port,
        username=ds.username,
        database=ds.database,
        schema_whitelist=ds.schema_whitelist,
        is_active=ds.is_active,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


def _get_encryption_key() -> str:
    settings = Settings()
    if not settings.encryption_key:
        raise HTTPException(status_code=500, detail="ENCRYPTION_KEY is not configured")
    return settings.encryption_key


async def _get_ds_or_404(ds_id: uuid.UUID, session: AsyncSession) -> DataSource:
    ds = await session.get(DataSource, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return ds


@router.post("", status_code=201)
async def create_data_source(
    payload: DataSourceCreate,
    session: SessionDep,
) -> DataSourceResponse:
    key = _get_encryption_key()
    existing = await session.execute(select(DataSource).where(DataSource.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Data source name already exists")

    ds = DataSource(
        name=payload.name,
        engine=payload.engine,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypt_value(payload.password, key),
        database=payload.database,
        schema_whitelist=payload.schema_whitelist,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return _model_to_response(ds)


@router.get("")
async def list_data_sources(session: SessionDep) -> list[DataSourceResponse]:
    result = await session.execute(select(DataSource).order_by(DataSource.created_at))
    datasources = result.scalars().all()
    return [_model_to_response(ds) for ds in datasources]


@router.get("/{ds_id}")
async def get_data_source(ds_id: uuid.UUID, session: SessionDep) -> DataSourceResponse:
    ds = await _get_ds_or_404(ds_id, session)
    return _model_to_response(ds)


@router.put("/{ds_id}")
async def update_data_source(
    ds_id: uuid.UUID,
    payload: DataSourceUpdate,
    session: SessionDep,
) -> DataSourceResponse:
    ds = await _get_ds_or_404(ds_id, session)
    update_data = payload.model_dump(exclude_unset=True)

    if "password" in update_data:
        key = _get_encryption_key()
        ds.password_encrypted = encrypt_value(update_data.pop("password"), key)

    if "name" in update_data:
        existing = await session.execute(
            select(DataSource).where(
                DataSource.name == update_data["name"],
                DataSource.id != ds_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Data source name already exists")

    for field, value in update_data.items():
        setattr(ds, field, value)

    await session.commit()
    await session.refresh(ds)
    return _model_to_response(ds)


@router.delete("/{ds_id}", status_code=204)
async def delete_data_source(ds_id: uuid.UUID, session: SessionDep) -> None:
    ds = await _get_ds_or_404(ds_id, session)
    await session.delete(ds)
    await session.commit()


@router.post("/{ds_id}/test")
async def test_connection(ds_id: uuid.UUID, session: SessionDep) -> ConnectionTestResponse:
    ds = await _get_ds_or_404(ds_id, session)
    key = _get_encryption_key()
    password = decrypt_value(ds.password_encrypted, key)

    try:
        from sqlalchemy import create_engine, text

        if ds.engine == "postgresql":
            sync_url = f"postgresql+psycopg2://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            sync_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"

        test_engine = create_engine(sync_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()

        return ConnectionTestResponse(success=True, message="Connection successful")
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))
