"""Integration tests for the marker-generation step inside `process_video_flow`.

These exercise `save_phrase_markers_task` (the side-effecting step that writes
`tokens` and pre-warms the autopsy cache) against the in-memory SQLite engine
from conftest. The marker service itself is mocked.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
import spacy
from sqlmodel import select

from flows import video_processing as flow_module
from models.database import PhraseAutopsy, Video, VideoSegment
from repositories.autopsy_repository import normalize_phrase
from services.phrase_markers import PhraseMarkersGenerationError


@pytest.fixture(autouse=True)
def patch_db_session(monkeypatch, session):
    """Route get_db_session() inside flows.video_processing to the test session."""

    @contextmanager
    def _ctx():
        yield session

    monkeypatch.setattr("flows.video_processing.get_db_session", _ctx)


@pytest.fixture(autouse=True)
def patch_nlp(monkeypatch):
    """Use a blank Spanish pipeline — fast, no transformer load."""
    nlp = spacy.blank("es")
    monkeypatch.setattr("flows.video_processing.get_nlp", lambda: nlp)


@pytest.fixture
def video_with_segment(session):
    video = Video(
        youtube_id="abc123",
        youtube_url="https://youtu.be/abc123",
        title="Test",
        duration=60,
        transcript="full",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    seg = VideoSegment(
        video_id=video.id,
        segment_number=0,
        transcript_text="Mira, no me da igual.",
        start_time=0.0,
        end_time=4.0,
    )
    session.add(seg)
    session.commit()
    session.refresh(seg)
    return video, seg


def _marker(phrase="no me da igual", segment_number=0):
    return {
        "phrase": phrase,
        "segment_number": segment_number,
        "tokens_in_segment": phrase.split(),
        "register": "coloquial · enfático",
        "grammar": [
            {"tag": "negación", "text": "«no» niega el verbo principal."},
            {"tag": "verbo impersonal", "text": "«da igual» tiene sujeto fijo."},
        ],
        "natural_notes": [
            "Suena a réplica viva.",
            "Más cálido que «me importa».",
        ],
    }


def test_save_phrase_markers_populates_tokens_and_autopsy(session, video_with_segment):
    video, seg = video_with_segment
    flow_module.save_phrase_markers_task.fn(video.id, [_marker()])

    refreshed = session.get(VideoSegment, seg.id)
    assert refreshed.tokens is not None
    parsed = json.loads(refreshed.tokens)
    span_tokens = [t for t in parsed if t.get("span") == 0]
    assert [t["t"] for t in span_tokens] == ["no", "me", "da", "igual"]
    assert any(t.get("start") for t in span_tokens)

    rows = session.exec(select(PhraseAutopsy).where(PhraseAutopsy.video_id == video.id)).all()
    assert len(rows) == 1
    assert rows[0].phrase_key == normalize_phrase("no me da igual")
    assert rows[0].start_time == seg.start_time
    assert rows[0].register == "coloquial · enfático"


def test_save_phrase_markers_no_markers_still_writes_plain_tokens(session, video_with_segment):
    video, seg = video_with_segment
    flow_module.save_phrase_markers_task.fn(video.id, [])

    refreshed = session.get(VideoSegment, seg.id)
    assert refreshed.tokens is not None
    parsed = json.loads(refreshed.tokens)
    assert all("span" not in t for t in parsed)
    assert any(t.get("t") == "Mira" for t in parsed)

    rows = session.exec(select(PhraseAutopsy).where(PhraseAutopsy.video_id == video.id)).all()
    assert rows == []


def test_pre_existing_autopsy_row_wins(session, video_with_segment):
    video, seg = video_with_segment

    # Simulate a manual tap that already cached this autopsy with custom data.
    pre = PhraseAutopsy(
        video_id=video.id,
        phrase="no me da igual",
        phrase_key=normalize_phrase("no me da igual"),
        start_time=seg.start_time,
        register="manual · pre-existing",
        grammar=json.dumps([{"tag": "x", "text": "y"}], ensure_ascii=False),
        natural_notes=json.dumps(["pre"], ensure_ascii=False),
    )
    session.add(pre)
    session.commit()

    flow_module.save_phrase_markers_task.fn(video.id, [_marker()])

    rows = session.exec(select(PhraseAutopsy).where(PhraseAutopsy.video_id == video.id)).all()
    assert len(rows) == 1
    assert rows[0].register == "manual · pre-existing"  # not overwritten


def test_marker_service_failure_returns_empty_list(monkeypatch, video_with_segment):
    video, _seg = video_with_segment

    def _raise(*args, **kwargs):
        raise PhraseMarkersGenerationError("boom")

    monkeypatch.setattr("flows.video_processing.phrase_markers_service.explain_video", _raise)

    out = flow_module.generate_phrase_markers_task.fn(video.id)
    assert out == []


def test_marker_service_success_returns_parsed_list(monkeypatch, video_with_segment):
    video, _seg = video_with_segment

    monkeypatch.setattr(
        "flows.video_processing.phrase_markers_service.explain_video",
        lambda segments: [_marker()],
    )

    out = flow_module.generate_phrase_markers_task.fn(video.id)
    assert len(out) == 1
    assert out[0]["phrase"] == "no me da igual"
