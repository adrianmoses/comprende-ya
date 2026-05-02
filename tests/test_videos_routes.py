"""Route tests for the /api/videos endpoints touched by PR #2 (012, persistence)."""

from datetime import datetime

from sqlmodel import select


def _stub_flow_returns(video_id: int):
    """Build a stub for process_video_flow that returns a dict shaped like the live one."""

    def _stub(url, force=False):
        return {
            "id": video_id,
            "video_id": "vid-x",
            "title": "stub",
            "duration": 60,
            "url": url,
            "transcript": "...",
            "questions": [],
            "exercise_count": 0,
        }

    return _stub


def _stub_flow_raises(message: str):
    def _stub(url, force=False):
        raise RuntimeError(message)

    return _stub


def test_process_async_happy_path(client, session, monkeypatch):
    from models.database import ProcessingJob, Video

    # Pre-seed a Video so mark_completed can set video_id without violating the FK.
    video = Video(
        youtube_id="abc12345678",
        youtube_url="https://youtu.be/abc12345678",
        title="t",
        duration=60,
        transcript="...",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    monkeypatch.setattr("api.routes.videos.process_video_flow", _stub_flow_returns(video.id))

    # Use a different youtube_id so the EXISTS dedup path is NOT triggered.
    response = client.post(
        "/api/videos/process-async",
        json={"url": "https://www.youtube.com/watch?v=NEW12345678"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    flow_run_id = body["flow_run_id"]
    assert flow_run_id is not None

    # BackgroundTasks run synchronously after the response; row should now be COMPLETED.
    job = session.exec(
        select(ProcessingJob).where(ProcessingJob.flow_run_id == flow_run_id)
    ).first()
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.youtube_video_id == "NEW12345678"


def test_process_async_failure_path(client, session, monkeypatch):
    from models.database import ProcessingJob

    monkeypatch.setattr(
        "api.routes.videos.process_video_flow", _stub_flow_raises("boom: yt-dlp 403")
    )

    response = client.post(
        "/api/videos/process-async",
        json={"url": "https://www.youtube.com/watch?v=FAIL12345678"},
    )
    assert response.status_code == 200
    flow_run_id = response.json()["flow_run_id"]

    job = session.exec(
        select(ProcessingJob).where(ProcessingJob.flow_run_id == flow_run_id)
    ).first()
    assert job.status == "FAILED"
    assert "boom" in job.error
    assert job.video_id is None


def test_status_404_with_corrected_message(client):
    response = client.get("/api/videos/status/no-such-flow")
    assert response.status_code == 404
    assert response.json()["detail"] == "Flow no encontrado"


def test_status_completed_shape(client, session):
    from models.database import ProcessingJob, Video

    video = Video(
        youtube_id="zzz12345678",
        youtube_url="https://youtu.be/zzz12345678",
        title="t",
        duration=60,
        transcript="...",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    job = ProcessingJob(
        flow_run_id="fr-completed",
        youtube_url="https://youtu.be/zzz12345678",
        youtube_video_id="zzz12345678",
        status="COMPLETED",
        video_id=video.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(job)
    session.commit()

    response = client.get("/api/videos/status/fr-completed")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "flow_run_id": "fr-completed",
        "status": "COMPLETED",
        "url": "https://youtu.be/zzz12345678",
        "youtube_video_id": "zzz12345678",
        "video_id": video.id,
    }
    assert "result" not in body  # explicitly dropped in PR #2
    assert "error" not in body  # only present on FAILED


def test_flows_pagination_newest_first(client, session):
    from models.database import ProcessingJob

    for i in range(3):
        session.add(
            ProcessingJob(
                flow_run_id=f"fr-{i}",
                youtube_url=f"https://x/{i}",
                youtube_video_id=f"v{i}",
                status="COMPLETED",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

    response = client.get("/api/videos/flows?skip=0&limit=2")
    assert response.status_code == 200
    flows = response.json()["flows"]
    assert len(flows) == 2
    # Newest first
    assert flows[0]["flow_run_id"] == "fr-2"
    assert flows[1]["flow_run_id"] == "fr-1"


def test_exists_short_circuit_creates_no_row(client, session):
    from models.database import ProcessingJob, Video

    # Pre-seed a video with the same youtube_id the request will extract.
    session.add(
        Video(
            youtube_id="EXISTS123456",
            youtube_url="https://youtu.be/EXISTS123456",
            title="cached",
            duration=60,
            transcript="...",
        )
    )
    session.commit()

    response = client.post(
        "/api/videos/process-async",
        json={"url": "https://www.youtube.com/watch?v=EXISTS123456"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["flow_run_id"] is None
    assert body["status"] == "EXISTS"

    # Verify no processing_jobs row landed.
    rows = session.exec(
        select(ProcessingJob).where(ProcessingJob.youtube_video_id == "EXISTS123456")
    ).all()
    assert rows == []
