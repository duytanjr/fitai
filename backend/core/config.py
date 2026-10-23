from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator


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

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SECRET_KEY is required and cannot be empty.")
        return v

    # Database (Docker Compose helpers — kept here for reference)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fitai_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fitai_db"

    # Google Gemini AI
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # Đổi model embedding thì phải chạy lại ingest với --reset (vector cũ không còn so sánh được)
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "fitai_knowledge"

    # RAG
    KNOWLEDGE_DIR: str = "data/knowledge"
    RAG_TOP_K: int = 5
    # Ngưỡng độ tương đồng cosine (1 - khoảng cách); tạm thời, chốt sau khi chạy rag_smoke
    RAG_SIMILARITY_THRESHOLD: float = 0.65

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []


settings = Settings()
