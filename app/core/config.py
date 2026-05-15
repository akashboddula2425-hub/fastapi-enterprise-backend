import json
from functools import lru_cache
from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "FastAPI Enterprise"
    app_env: str = "development"
    debug: bool = False
    secret_key: str
    # Stored as a raw string so pydantic-settings doesn't try to JSON-decode it.
    # Parsed via `allowed_origins` below — accepts comma-separated or JSON list.
    allowed_origins_raw: str = "http://localhost:3000"

    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    # Auth
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @computed_field
    @property
    def allowed_origins(self) -> List[str]:
        v = (self.allowed_origins_raw or "").strip()
        if not v:
            return []
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                return [str(x) for x in parsed]
            except json.JSONDecodeError:
                return []
        return [item.strip() for item in v.split(",") if item.strip()]

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Synchronous URL for Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
