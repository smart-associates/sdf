import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import DatabaseConnection
from app.schemas.connection import (
    DatabaseConnectionCreate, DatabaseConnectionUpdate,
    DatabaseConnectionResponse, ConnectionTestResponse,
    ConnectionExportItem, ConnectionExportDocument, ConnectionImportResult, ConnectionImportFailure,
)
from app.services import connection_service as svc
from app.services import connection_introspect

router = APIRouter(prefix="/api/connections", tags=["connections"])

@router.get("", response_model=list[DatabaseConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db)):
    return await svc.list_connections(db)

@router.get("/export", response_model=ConnectionExportDocument)
async def export_all_connections(db: AsyncSession = Depends(get_db)):
    """Registered before GET /{conn_id} — otherwise FastAPI would try to parse
    'export' as a conn_id and 404 rather than reaching this handler."""
    conns = await svc.list_connections(db)
    items = [ConnectionExportItem.model_validate(c) for c in conns]
    return ConnectionExportDocument(exported_at=datetime.now(timezone.utc), connections=items)

@router.get("/{conn_id}/export", response_model=ConnectionExportDocument)
async def export_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await svc.get_connection(db, conn_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    item = ConnectionExportItem.model_validate(conn)
    return ConnectionExportDocument(exported_at=datetime.now(timezone.utc), connections=[item])

@router.post("/import", response_model=ConnectionImportResult)
async def import_connections(doc: ConnectionExportDocument, db: AsyncSession = Depends(get_db)):
    """Import a connection export document.

    Two phases: resolve everything first (by name — an existing connection
    with a different db_type is a field to update, not a different identity)
    and fail the whole request if any name is ambiguous, before writing
    anything; then apply by calling create_connection/update_connection
    directly so import gets the same validation as the regular endpoints,
    for free.
    """
    if doc.format_version != 1:
        raise HTTPException(400, f"Unsupported export format_version {doc.format_version}")

    problems: list = []
    plan: list = []
    for item in doc.connections:
        result = await db.execute(select(DatabaseConnection).where(DatabaseConnection.name == item.name))
        matches = result.scalars().all()
        if len(matches) > 1:
            problems.append(f"connection '{item.name}' is ambiguous ({len(matches)} matches on this instance)")
            continue
        plan.append((item, matches[0] if matches else None))

    if problems:
        raise HTTPException(400, "; ".join(problems))

    result = ConnectionImportResult()
    for item, existing in plan:
        try:
            if existing is None:
                data = DatabaseConnectionCreate(**item.model_dump())
                await svc.create_connection(db, data.model_dump())
                result.created.append(item.name)
            else:
                data = DatabaseConnectionUpdate(**item.model_dump())
                await svc.update_connection(db, existing.id, data.model_dump(exclude_unset=True))
                result.updated.append(item.name)
        except (HTTPException, ValidationError) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            result.failed.append(ConnectionImportFailure(name=item.name, error=str(detail)))

    return result

@router.get("/{conn_id}", response_model=DatabaseConnectionResponse)
async def get_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await svc.get_connection(db, conn_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    return conn

@router.post("", response_model=DatabaseConnectionResponse, status_code=201)
async def create_connection(data: DatabaseConnectionCreate, db: AsyncSession = Depends(get_db)):
    return await svc.create_connection(db, data.model_dump())

@router.put("/{conn_id}", response_model=DatabaseConnectionResponse)
async def update_connection(conn_id: int, data: DatabaseConnectionUpdate, db: AsyncSession = Depends(get_db)):
    conn = await svc.update_connection(db, conn_id, data.model_dump(exclude_unset=True))
    if not conn:
        raise HTTPException(404, "Connection not found")
    return conn

@router.delete("/{conn_id}", status_code=204)
async def delete_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    try:
        if not await svc.delete_connection(db, conn_id):
            raise HTTPException(404, "Connection not found")
    except ValueError as e:
        raise HTTPException(409, str(e))

@router.post("/{conn_id}/test", response_model=ConnectionTestResponse)
async def test_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await svc.test_connection(db, conn_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{conn_id}/clone", response_model=DatabaseConnectionResponse, status_code=201)
async def clone_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    clone = await svc.clone_connection(db, conn_id)
    if not clone:
        raise HTTPException(404, "Connection not found")
    return clone

@router.get("/{conn_id}/schemas")
async def list_connection_schemas(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await svc.get_connection_raw(db, conn_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    try:
        schemas = await connection_introspect.list_schemas(conn)
    except connection_introspect.IntrospectError as e:
        raise HTTPException(400, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(504, f"Schema listing timed out after {connection_introspect.INTROSPECT_TIMEOUT}s")
    except Exception as e:
        raise HTTPException(502, f"Could not list schemas: {str(e)[:255]}")
    return {"schemas": schemas}

@router.get("/{conn_id}/objects")
async def list_connection_objects(conn_id: int, schema: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    conn = await svc.get_connection_raw(db, conn_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    try:
        objects = await connection_introspect.list_objects(conn, schema=schema)
    except connection_introspect.IntrospectError as e:
        raise HTTPException(400, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(504, f"Object listing timed out after {connection_introspect.INTROSPECT_TIMEOUT}s")
    except Exception as e:
        raise HTTPException(502, f"Could not list objects: {str(e)[:255]}")
    return {"objects": objects}

@router.get("/{conn_id}/files")
async def list_connection_files(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await svc.get_connection_raw(db, conn_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    try:
        files = await connection_introspect.list_files(conn)
    except connection_introspect.IntrospectError as e:
        raise HTTPException(400, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(504, f"File listing timed out after {connection_introspect.INTROSPECT_TIMEOUT}s")
    except Exception as e:
        raise HTTPException(502, f"Could not list files: {str(e)[:255]}")
    return {"files": files}
