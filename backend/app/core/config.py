import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", 8000))

    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "graphrag")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "storage/uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50))

    # Neo4j Settings
    ENABLE_NEO4J: bool = os.getenv("ENABLE_NEO4J", "false").lower() in ("true", "1", "yes")
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

    # Gemini Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
    GEMINI_LLM_MODEL: str = os.getenv("GEMINI_LLM_MODEL", "gemini-3.5-flash-lite")
    GEMINI_EMBEDDING_DIMENSION: int = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", 768))

    # Cohere Settings
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_RERANK_MODEL: str = os.getenv("COHERE_RERANK_MODEL", "rerank-multilingual-v3.0")
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", 5))

    # Auth & JWT Settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "knowledge_loader_super_secret_jwt_key_2026_x89a")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))  # 7 days
    INITIAL_ADMIN_USERNAME: str = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")

    # Mock Mode for Performance Benchmark / Load Testing
    MOCK_AI_SERVICES: bool = os.getenv("MOCK_AI_SERVICES", "false").lower() in ("true", "1", "yes")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
