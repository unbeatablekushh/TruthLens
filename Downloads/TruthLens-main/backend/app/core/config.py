from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TruthLens API"
    
    # Postgres
    POSTGRES_USER: str = "truthlens"
    POSTGRES_PASSWORD: str = "truthlens_pass"
    POSTGRES_DB: str = "truthlens"
    DATABASE_URL: str = "sqlite:///./truthlens.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Auth
    JWT_SECRET: str = "super_secret_development_key"
    JWT_REFRESH_SECRET: str = "super_secret_development_refresh_key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting
    AUTH_LOGIN_RATE_LIMIT: str = "5/minute"
    AUTH_REGISTER_RATE_LIMIT: str = "3/minute"
    
    # AI/Search
    AI_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:8b"
    
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    SEARCH_PROVIDER: str = "searxng"
    SEARXNG_BASE_URL: str = "http://localhost:8080/"
    
    DEMO_MODE: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
