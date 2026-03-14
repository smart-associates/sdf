from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, unique=True)
    value = Column(Text)
    description = Column(Text)
    data_type = Column(String(50), nullable=False, default="string")  # string|integer|boolean
