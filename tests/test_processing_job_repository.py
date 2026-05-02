"""End-to-end tests for ProcessingJobRepository against the in-memory fixture."""

import time

from repositories import ProcessingJobRepository


def test_create_pending_populates_defaults(session):
    repo = ProcessingJobRepository(session)
    job = repo.create_pending(
        flow_run_id="fr-1",
        youtube_url="https://youtu.be/abc",
        youtube_video_id="abc",
    )
    assert job.id is not None
    assert job.flow_run_id == "fr-1"
    assert job.status == "PENDING"
    assert job.youtube_video_id == "abc"
    assert job.error is None
    assert job.video_id is None
    assert job.created_at is not None
    assert job.updated_at is not None


def test_lifecycle_transitions(session):
    from models.database import Video

    # Pre-seed a Video so the FK on processing_jobs.video_id has a target.
    video = Video(
        youtube_id="vid2",
        youtube_url="https://x",
        title="t",
        duration=60,
        transcript="...",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    repo = ProcessingJobRepository(session)
    repo.create_pending(flow_run_id="fr-2", youtube_url="https://x", youtube_video_id="vid2")

    # mark_running keeps timestamps moving forward
    time.sleep(0.001)  # ensure datetime.utcnow() resolves a different value
    running = repo.mark_running("fr-2")
    assert running.status == "RUNNING"
    assert running.updated_at >= running.created_at

    # mark_completed sets video_id
    completed = repo.mark_completed("fr-2", video_id=video.id)
    assert completed.status == "COMPLETED"
    assert completed.video_id == video.id
    assert completed.error is None


def test_mark_completed_without_video_id(session):
    """video_id is optional on mark_completed — common path when flow returns None."""
    repo = ProcessingJobRepository(session)
    repo.create_pending(flow_run_id="fr-2b", youtube_url="https://x", youtube_video_id="vid2b")
    completed = repo.mark_completed("fr-2b")
    assert completed.status == "COMPLETED"
    assert completed.video_id is None


def test_mark_failed_records_error_string(session):
    repo = ProcessingJobRepository(session)
    repo.create_pending(flow_run_id="fr-3", youtube_url="https://x", youtube_video_id="vid3")
    failed = repo.mark_failed("fr-3", error="boom: yt-dlp 403")
    assert failed.status == "FAILED"
    assert failed.error == "boom: yt-dlp 403"
    assert failed.video_id is None


def test_get_by_flow_run_id_missing_returns_none(session):
    repo = ProcessingJobRepository(session)
    assert repo.get_by_flow_run_id("does-not-exist") is None


def test_set_status_no_op_when_row_missing(session):
    """Transition methods on a missing flow_run_id return None instead of raising."""
    repo = ProcessingJobRepository(session)
    assert repo.mark_running("missing") is None
    assert repo.mark_completed("missing", video_id=1) is None
    assert repo.mark_failed("missing", error="x") is None


def test_list_orders_newest_first_and_paginates(session):
    repo = ProcessingJobRepository(session)
    # Insert in chronological order; expect reverse-chronological listing.
    for i in range(5):
        repo.create_pending(
            flow_run_id=f"fr-list-{i}",
            youtube_url=f"https://x/{i}",
            youtube_video_id=f"vid{i}",
        )
        time.sleep(0.001)

    page = repo.list(skip=0, limit=3)
    assert len(page) == 3
    ids = [j.flow_run_id for j in page]
    assert ids == ["fr-list-4", "fr-list-3", "fr-list-2"]

    page2 = repo.list(skip=3, limit=3)
    assert [j.flow_run_id for j in page2] == ["fr-list-1", "fr-list-0"]
