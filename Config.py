from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "EchoChat"
    APP_VERSION: str = "1.0.0"

    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/echochat.db"
    OLLAMA_URL: str = "http://localhost:11434/v1/chat/completions"
    OLLAMA_MODEL: str = "llama3.1:8b"
    AI_CACHE_SIZE: int = 500
    AI_CACHE_TTL: int = 3600

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    MEDIA_ENCRYPTION_KEY: str    # 64 hex chars

    ECHOCHAT_STORAGE: str = "local"
    LOCAL_MEDIA_ROOT: str = str(BASE_DIR / "media")
    LOCAL_MEDIA_URL_PREFIX: str = "/media/"

    ENABLE_SAFETY_CHECK: bool = True
    DAILY_AI_LIMIT_PER_USER: int = 200

    JITSI_DOMAIN: str = "meet.yourdomain.com"

    LOG_LEVEL: str = "INFO"

    # Frontend API base (used by Flet)
    API_BASE: str = "http://localhost:8000"

    # CORS origins (comma-separated)
    CORS_ORIGINS: str = "http://localhost:8550,http://localhost:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
