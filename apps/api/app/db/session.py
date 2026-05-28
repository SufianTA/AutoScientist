from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "runs" not in tables:
        return
    table_columns = {
        "runs": {
            "run_config_json": "JSON DEFAULT '{}'",
            "agent_count": "INTEGER DEFAULT 6",
            "max_runtime_minutes": "INTEGER DEFAULT 30",
            "estimated_cost_usd": "FLOAT DEFAULT 0.0",
            "account_id": "VARCHAR",
            "payment_status": "VARCHAR(40) DEFAULT 'not_required'",
            "queued_at": "DATETIME",
            "project_id": "VARCHAR",
        },
        "objectives": {
            "project_id": "VARCHAR",
        },
        "tool_calls": {
            "project_id": "VARCHAR",
        },
        "evidence_items": {
            "project_id": "VARCHAR",
        },
        "hypotheses": {
            "project_id": "VARCHAR",
        },
        "board_posts": {
            "project_id": "VARCHAR",
        },
    }
    with engine.begin() as connection:
        for table, columns in table_columns.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
