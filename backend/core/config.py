from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",   # ignore vars like POSTGRES_USER used only by docker-compose
    )

    # Application
    APP_NAME: str = "FitAI Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "changeme"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database (Docker Compose helpers — kept here for reference)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fitai_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fitai_db"

    # Google Gemini AI
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "fitai_knowledge"

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []


settings = Settings()
