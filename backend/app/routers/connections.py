from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.connection import (
    DatabaseConnectionCreate, DatabaseConnectionUpdate,
    DatabaseConnectionResponse, ConnectionTestResponse
)
from app.services import connection_service as svc

router = APIRouter(prefix="/api/connections", tags=["connections"])

@router.get("", response_model=list[DatabaseConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db)):
    return await svc.list_connections(db)

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
