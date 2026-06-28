# Stub env vars BEFORE any project import — src/config.py:18-23 raises at
# import time if any of ANTHROPIC_API_KEY / OPENAI_API_KEY / YOUTUBE_API_KEY
# is missing, and that side effect propagates through every module that
# imports `settings` (services, repos, db, routes).
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube")
os.environ.setdefault("PREFECT_API_URL", "http://localhost:0")

# Tests run against a REAL Postgres (parity with prod — no SQLite dialect drift).
# DATABASE_URL_TEST overrides (CI points it at a services-postgres); the default is
# a local comprende_ya_test database. Force-set DATABASE_URL so settings/db/alembic
# all see the test DB, not whatever the shell exported.
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql://postgres:postgres@localhost:5432/comprende_ya_test",
)

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlmodel import Session, SQLModel

# Populate SQLModel.metadata (drop_all / truncate below need every table registered).
from db import engine as db_engine
from models import database  # noqa: F401

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Build the schema once per session from the Alembic baseline, on a clean slate."""
    SQLModel.metadata.drop_all(db_engine)
    with db_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _isolate(_schema):
    """Per-test isolation: wipe all tables after each test. Repos commit, so a
    transaction rollback wouldn't undo their writes — TRUNCATE does."""
    yield
    tables = ", ".join(f'"{t.name}"' for t in SQLModel.metadata.sorted_tables)
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def engine(_schema):
    """The Postgres engine (built from settings.DATABASE_URL == the test DB)."""
    return db_engine


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def app(session, monkeypatch):
    """FastAPI app wired to the test session for both Depends() and BackgroundTasks paths."""
    from contextlib import contextmanager

    from db import get_session
    from main import app as fastapi_app

    fastapi_app.dependency_overrides[get_session] = lambda: session

    # Patch the context manager that BackgroundTasks uses inside run_flow_background.
    # The patch target is api.routes.videos.get_db_session (where the symbol is
    # bound at import time via `from db import get_db_session`), NOT db.get_db_session.
    @contextmanager
    def _ctx():
        yield session

    monkeypatch.setattr("api.routes.videos.get_db_session", _ctx)

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def seeded_video(session):
    """Insert a video + 2 segments matching the seeded m1DFpkNdcv0 fixture."""
    from models.database import Video, VideoSegment

    video = Video(
        youtube_id="m1DFpkNdcv0",
        youtube_url="https://youtu.be/m1DFpkNdcv0",
        title="Vídeo de prueba",
        duration=300,
        transcript="Quedamos a eso de las nueve. Yo creo que para entonces ya habré salido.",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    session.add_all(
        [
            VideoSegment(
                video_id=video.id,
                segment_number=1,
                transcript_text="Quedamos a eso de las nueve.",
                start_time=10.0,
                end_time=14.0,
            ),
            VideoSegment(
                video_id=video.id,
                segment_number=2,
                transcript_text="Yo creo que para entonces ya habré salido.",
                start_time=14.0,
                end_time=18.0,
            ),
        ]
    )
    session.commit()
    return video
