from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.setting import Setting
from app.schemas.setting import SettingCreate, SettingUpdate, SettingResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("", response_model=list[SettingResponse])
async def list_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).order_by(Setting.id))
    return result.scalars().all()

@router.get("/{setting_id}", response_model=SettingResponse)
async def get_setting(setting_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.id == setting_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Setting not found")
    return s

@router.post("", response_model=SettingResponse, status_code=201)
async def create_setting(data: SettingCreate, db: AsyncSession = Depends(get_db)):
    s = Setting(**data.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

@router.put("/{setting_id}", response_model=SettingResponse)
async def update_setting(setting_id: int, data: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.id == setting_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Setting not found")
    for k, v in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return s

@router.delete("/{setting_id}", status_code=204)
async def delete_setting(setting_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.id == setting_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Setting not found")
    await db.delete(s)
    await db.commit()
