"""Sanity tests for the conftest engine/session fixtures.

Run against real Postgres (029): the Alembic baseline applies, the CHECK constraint
on processing_jobs.status fires, and FK ON DELETE SET NULL works — now validated by
the production engine rather than SQLite.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def test_all_tables_present(engine):
    """Every model the audit identified should land in the test DB."""
    expected = {
        "videos",
        "questions",
        "video_segments",
        "answer_progress",
        "frase_exercise",
        "processing_jobs",
        "phrase_autopsy",
        "chunks",
        "recordings",
        "alembic_version",
    }
    actual = set(inspect(engine).get_table_names())
    missing = expected - actual
    assert not missing, f"missing tables: {missing}"


def test_processing_jobs_status_check_constraint(engine):
    """The CHECK constraint is declared on the model (029) — assert Postgres enforces it."""
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO processing_jobs "
                    "(flow_run_id, youtube_url, youtube_video_id, status, "
                    " created_at, updated_at) "
                    "VALUES ('abc', 'https://x', 'vid', 'NOPE', "
                    "'2026-05-02', '2026-05-02')"
                )
            )


def test_processing_jobs_fk_set_null_on_video_delete(engine):
    """video_id is FK ON DELETE SET NULL; deleting the parent video must NULL the column."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos "
                "(youtube_id, youtube_url, title, duration, transcript, "
                " created_at, updated_at) "
                "VALUES ('yt1', 'https://x', 't', 60, '...', "
                "'2026-05-02', '2026-05-02')"
            )
        )
        video_id = conn.execute(text("SELECT id FROM videos WHERE youtube_id='yt1'")).scalar()
        conn.execute(
            text(
                "INSERT INTO processing_jobs "
                "(flow_run_id, youtube_url, youtube_video_id, status, video_id, "
                " created_at, updated_at) "
                f"VALUES ('fr1', 'https://x', 'yt1', 'COMPLETED', {video_id}, "
                "'2026-05-02', '2026-05-02')"
            )
        )
        conn.execute(text("DELETE FROM videos WHERE id = :i"), {"i": video_id})
        result = conn.execute(
            text("SELECT video_id FROM processing_jobs WHERE flow_run_id='fr1'")
        ).scalar()
        assert result is None, "expected video_id to be SET NULL after parent delete"
