from pydantic import BaseModel
from typing import Optional

class SettingBase(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    data_type: str = "string"

class SettingCreate(SettingBase):
    pass

class SettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None

class SettingResponse(SettingBase):
    id: int

    class Config:
        from_attributes = True
