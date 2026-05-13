"""Route tests for `GET /api/videos/{video_id}/segments` (018: tokens field)."""

from __future__ import annotations

import json


def _seed_video_with_segments(session, *, tokens_for_first: str | None) -> int:
    from models.database import Video, VideoSegment

    video = Video(
        youtube_id="seg12345678",
        youtube_url="https://youtu.be/seg12345678",
        title="t",
        duration=60,
        transcript="...",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    session.add(
        VideoSegment(
            video_id=video.id,
            segment_number=0,
            transcript_text="Mira, no me da igual.",
            start_time=0.0,
            end_time=4.0,
            tokens=tokens_for_first,
        )
    )
    session.add(
        VideoSegment(
            video_id=video.id,
            segment_number=1,
            transcript_text="Pero bueno, sigamos.",
            start_time=4.0,
            end_time=8.0,
            tokens=None,
        )
    )
    session.commit()
    return video.id


def test_segments_response_includes_tokens_when_set(client, session):
    tokens_payload = [
        {"t": "Mira"},
        {"p": ","},
        {"t": "no", "span": 0, "start": True},
        {"t": "me", "span": 0},
        {"t": "da", "span": 0},
        {"t": "igual", "span": 0},
        {"p": "."},
    ]
    video_id = _seed_video_with_segments(
        session, tokens_for_first=json.dumps(tokens_payload, ensure_ascii=False)
    )

    response = client.get(f"/api/videos/{video_id}/segments")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["tokens"] == tokens_payload
    assert body[1]["tokens"] is None


def test_segments_response_includes_tokens_null_when_unset(client, session):
    video_id = _seed_video_with_segments(session, tokens_for_first=None)

    response = client.get(f"/api/videos/{video_id}/segments")
    assert response.status_code == 200
    body = response.json()
    for seg in body:
        assert seg["tokens"] is None
