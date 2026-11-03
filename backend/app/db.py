from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


settings = get_settings()
database_url = settings.resolved_database_url
engine = create_engine(database_url, future=True, **_engine_kwargs(database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_schema_compatibility() -> None:
    """Apply additive local-schema changes without resetting existing data."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "alert_events" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("alert_events")}
    if "created_at" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE alert_events ADD COLUMN created_at DATETIME"))
    with engine.begin() as connection:
        connection.execute(text("UPDATE alert_events SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
