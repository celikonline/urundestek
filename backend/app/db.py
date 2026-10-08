from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import ROOT, settings


class Base(DeclarativeBase):
    pass


if settings.database_url.startswith("sqlite"):
    (ROOT / "data").mkdir(exist_ok=True)
options = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {}
if settings.database_url in ("sqlite://", "sqlite:///:memory:"):
    options["poolclass"] = StaticPool
engine = create_engine(settings.database_url, pool_pre_ping=True, **options)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
