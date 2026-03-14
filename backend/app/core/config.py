from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sdf"
    sync_database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/sdf"
    encryption_key: str = "change-me-32-char-key-for-prod!!"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
