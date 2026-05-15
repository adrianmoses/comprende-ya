# Stub env vars BEFORE any project import — src/config.py:18-23 raises at
# import time if any of ANTHROPIC_API_KEY / OPENAI_API_KEY / YOUTUBE_API_KEY
# is missing, and that side effect propagates through every module that
# imports `settings` (services, repos, db, routes).
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube")
os.environ.setdefault("PREFECT_API_URL", "http://localhost:0")

# DB url is force-set (not setdefault) — alembic/env.py:23 sets the URL on the
# Config object from settings.DATABASE_URL, so we need settings to see SQLite,
# not whatever the developer's shell happens to have exported.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session


@pytest.fixture
def engine():
    """In-memory SQLite engine with FK enforcement and Alembic schema applied."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk_pragma(dbapi_conn, _):
        # ON DELETE SET NULL needs FK enforcement, off by default in SQLite.
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")

    yield eng


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
