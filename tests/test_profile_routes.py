"""Tests for the /api/profile endpoints + KPI aggregates (022)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlmodel import select

from repositories.profile_repository import _week_start_utc


def _add_answer(session, video_id, *, is_correct, answered_at):
    """Create a fresh Question + an AnswerProgress for it (the unique
    (video_id, question_id) constraint needs a distinct question per answer)."""
    from models.database import AnswerProgress, Question

    q = Question(
        video_id=video_id,
        timestamp=1.0,
        question="¿Qué significa?",
        answers=json.dumps(["a", "b", "c", "d"]),
        correct_answer=0,
    )
    session.add(q)
    session.commit()
    session.refresh(q)

    ap = AnswerProgress(
        video_id=video_id,
        question_id=q.id,
        user_answer=0,
        is_correct=is_correct,
        answered_at=answered_at,
    )
    session.add(ap)
    session.commit()
    return ap


def _add_study_session(session, *, seconds, created_at):
    from models.database import StudySession

    row = StudySession(seconds=seconds, created_at=created_at)
    session.add(row)
    session.commit()
    return row


# --- profile identity -------------------------------------------------------


def test_get_profile_lazily_creates_defaults(client, session):
    from models.database import Profile

    response = client.get("/api/profile")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Ana"
    assert body["level"] == "B2"
    assert body["week_minutes"] == 0
    assert body["streak"] == 0
    assert body["dia"] == 0
    assert body["comprehension"] is None

    # The singleton row was persisted exactly once, at id=1.
    rows = session.exec(select(Profile)).all()
    assert len(rows) == 1
    assert rows[0].id == 1


def test_put_profile_updates_name_and_level(client):
    response = client.put("/api/profile", json={"name": "Adrián", "level": "C1"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Adrián"
    assert response.json()["level"] == "C1"

    # Persisted across reads.
    assert client.get("/api/profile").json()["name"] == "Adrián"


def test_put_profile_partial_update_keeps_other_field(client):
    client.put("/api/profile", json={"name": "Adrián", "level": "C1"})
    response = client.put("/api/profile", json={"name": "Ana"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Ana"
    assert response.json()["level"] == "C1"  # untouched


# --- session write path -----------------------------------------------------


def test_post_session_appends_row(client, session):
    from models.database import StudySession

    response = client.post("/api/profile/session", json={"seconds": 60})
    assert response.status_code == 204, response.text
    rows = session.exec(select(StudySession)).all()
    assert len(rows) == 1
    assert rows[0].seconds == 60


def test_post_session_rejects_non_positive_and_absurd(client):
    assert client.post("/api/profile/session", json={"seconds": 0}).status_code == 422
    assert client.post("/api/profile/session", json={"seconds": -5}).status_code == 422
    assert client.post("/api/profile/session", json={"seconds": 4000}).status_code == 422


# --- week minutes -----------------------------------------------------------


def test_week_minutes_sums_current_week_only(client, session):
    now = datetime.utcnow()
    _add_study_session(session, seconds=600, created_at=now)  # this week
    _add_study_session(session, seconds=200, created_at=now)  # this week
    _add_study_session(
        session, seconds=5000, created_at=now - timedelta(days=8)
    )  # prior week — excluded

    body = client.get("/api/profile").json()
    assert body["week_minutes"] == 13  # (600 + 200) // 60


def test_week_minutes_empty_is_zero(client):
    assert client.get("/api/profile").json()["week_minutes"] == 0


def test_week_minutes_boundary_is_inclusive_of_monday_midnight(client, session):
    start = _week_start_utc()
    _add_study_session(session, seconds=120, created_at=start)  # exactly Monday 00:00
    _add_study_session(
        session, seconds=999, created_at=start - timedelta(seconds=1)
    )  # last week — excluded
    assert client.get("/api/profile").json()["week_minutes"] == 2  # only the 120s


# --- comprehension ----------------------------------------------------------


def test_comprehension_null_when_no_answers(client):
    assert client.get("/api/profile").json()["comprehension"] is None


def test_comprehension_rounds_all_time_accuracy(client, session, seeded_video):
    now = datetime.utcnow()
    for _ in range(5):
        _add_answer(session, seeded_video.id, is_correct=True, answered_at=now)
    _add_answer(session, seeded_video.id, is_correct=False, answered_at=now)

    # 5/6 = 83.33% -> 83
    assert client.get("/api/profile").json()["comprehension"] == 83


# --- streak -----------------------------------------------------------------


def test_streak_zero_with_no_activity(client):
    assert client.get("/api/profile").json()["streak"] == 0


def test_streak_today_only_is_one(client, session):
    _add_study_session(session, seconds=60, created_at=datetime.utcnow())
    body = client.get("/api/profile").json()
    assert body["streak"] == 1
    assert body["dia"] == 1  # dia mirrors streak (OQ1)


def test_streak_counts_consecutive_days(client, session):
    now = datetime.utcnow()
    for d in (0, 1, 2):
        _add_study_session(session, seconds=60, created_at=now - timedelta(days=d))
    assert client.get("/api/profile").json()["streak"] == 3


def test_streak_breaks_on_gap(client, session):
    now = datetime.utcnow()
    # Activity only two days ago, nothing today/yesterday -> not current -> 0.
    _add_study_session(session, seconds=60, created_at=now - timedelta(days=2))
    assert client.get("/api/profile").json()["streak"] == 0


def test_streak_yesterday_grace(client, session):
    now = datetime.utcnow()
    # Studied yesterday, not yet today -> streak still current at 1 (day not over).
    _add_study_session(session, seconds=60, created_at=now - timedelta(days=1))
    assert client.get("/api/profile").json()["streak"] == 1


def test_streak_counts_mcq_only_day_as_active(client, session, seeded_video):
    now = datetime.utcnow()
    # No StudySession at all — only an answered MCQ today (OQ3).
    _add_answer(session, seeded_video.id, is_correct=True, answered_at=now)
    assert client.get("/api/profile").json()["streak"] == 1


def test_streak_mixes_sessions_and_answers_across_days(client, session, seeded_video):
    now = datetime.utcnow()
    _add_answer(session, seeded_video.id, is_correct=True, answered_at=now)  # today
    _add_study_session(session, seconds=60, created_at=now - timedelta(days=1))  # yesterday
    assert client.get("/api/profile").json()["streak"] == 2
