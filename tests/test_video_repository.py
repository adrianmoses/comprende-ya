"""Smoke test for VideoRepository — proves the fixture works for non-PR-#2 modules."""

from models.schemas import TimestampedQuestion
from repositories import VideoRepository


def test_create_then_get_by_youtube_id_round_trip(session):
    repo = VideoRepository(session)
    repo.create(
        youtube_id="abc12345678",
        youtube_url="https://youtu.be/abc12345678",
        title="Mercados de barrio",
        duration=872,
        transcript="full text…",
        questions=[
            TimestampedQuestion(
                timestamp=15.5,
                question="¿Qué pasa?",
                answers=["a", "b", "c", "d"],
                correct_answer=0,
                explanation="...",
            ),
        ],
    )

    fetched = repo.get_by_youtube_id("abc12345678")
    assert fetched is not None
    assert fetched.title == "Mercados de barrio"
    assert fetched.duration == 872
    assert len(fetched.questions) == 1
    assert fetched.questions[0].timestamp == 15.5
