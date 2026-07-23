from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "Denmark Academy"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql://denmark:denmark@localhost:5432/denmark_academy"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None  # Required for Qdrant Cloud

    object_storage_driver: str = "local"
    local_object_storage_path: Path = Path("object-storage")

    embedding_dimension: int = 384
    embedding_provider: str = "placeholder"
    parser_version: str = "pdf-parser-v1"

    ai_primary_provider: str = "grok"
    ai_fallback_provider: str = "gemini"
    ai_disable_gemini: bool = True
    ai_request_timeout_seconds: float = Field(default=60, ge=1, le=300)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    current_affairs_scheduler_enabled: bool = True
    current_affairs_rss_feeds: str = "DR Nyheder|https://www.dr.dk/nyheder/service/feeds/allenyheder"
    current_affairs_max_articles_per_run: int = Field(default=6, ge=1, le=25)

    # Multiple API Keys for Load Balancing
    # Grok API Keys (6 keys for better rotation)
    grok_api_key_1: SecretStr | None = None
    grok_api_key_2: SecretStr | None = None
    grok_api_key_3: SecretStr | None = None
    grok_api_key_4: SecretStr | None = None
    grok_api_key_5: SecretStr | None = None
    grok_api_key_6: SecretStr | None = None
    grok_base_url: str = "https://api.groq.com/openai/v1"
    grok_model: str = "llama-3.3-70b-versatile"

    # Gemini API Keys (3 keys for rotation) - DISABLED
    gemini_api_key_1: SecretStr | None = None
    gemini_api_key_2: SecretStr | None = None
    gemini_api_key_3: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.5-flash"
    
    # Security Configuration
    allowed_origins: str = "http://localhost:3001,http://localhost:3000"  # Comma-separated
    admin_api_key: SecretStr | None = None  # For protecting admin endpoints
    
    # Backward compatibility (uses first key)
    @property
    def grok_api_key(self) -> SecretStr | None:
        return self.grok_api_key_1
    
    @property
    def gemini_api_key(self) -> SecretStr | None:
        return self.gemini_api_key_1

    admin_email: str = Field(default="admin@denmark-academy.local")
    app_public_url: str = "http://localhost:3001"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str = "no-reply@denmark-academy.local"
    smtp_starttls: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


