from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = PROJECT_ROOT / "backend" / ".env"
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "smart_energy.db"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
    cors_origins: str = "http://localhost:5173"
    app_env: str = "development"
    page_size_default: int = 50
    page_size_max: int = 200

    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Return a stable SQLite URL while leaving RDS URLs unchanged."""
        if not self.database_url.startswith("sqlite:///"):
            return self.database_url

        raw_path = self.database_url.removeprefix("sqlite:///")
        if raw_path in {":memory:", ""}:
            return self.database_url
        database_path = Path(raw_path)
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path.resolve().as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
