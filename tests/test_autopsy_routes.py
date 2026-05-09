"""Tests for the /api/videos/{id}/autopsy endpoints."""

from __future__ import annotations

import json

import pytest
from sqlmodel import select

VALID_PAYLOAD = {
    "register": "cotidiano · neutral",
    "grammar": [
        {"tag": "preposición", "text": "«a» marca la hora puntual."},
        {"tag": "demostrativo neutro", "text": "«eso» es vago en el tiempo."},
    ],
    "natural_notes": [
        "Suena natural cuando la hora es aproximada.",
        "Más cálido que «a las nueve en punto».",
    ],
}


@pytest.fixture
def seeded_video(session):
    """Insert a video + 2 segments and return it."""
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


def _stub_explain_returning(payload):
    calls = []

    def _explain(phrase, context):
        calls.append({"phrase": phrase, "context": context})
        return payload

    _explain.calls = calls
    return _explain


def _stub_explain_raises(message):
    from services.phrase_autopsy import AutopsyGenerationError

    calls = []

    def _explain(phrase, context):
        calls.append({"phrase": phrase, "context": context})
        raise AutopsyGenerationError(message)

    _explain.calls = calls
    return _explain


def test_explain_cache_miss_calls_service_and_persists(client, session, seeded_video, monkeypatch):
    from models.database import PhraseAutopsy

    stub = _stub_explain_returning(VALID_PAYLOAD)
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    response = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "a eso de las nueve", "start_time": 12},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phrase"] == "a eso de las nueve"
    assert body["video_id"] == seeded_video.youtube_id
    assert body["register"] == "cotidiano · neutral"
    assert body["grammar"] == VALID_PAYLOAD["grammar"]
    assert body["natural_notes"] == VALID_PAYLOAD["natural_notes"]
    assert "id" in body and "created_at" in body

    assert len(stub.calls) == 1
    # Context window includes both seeded segments (start_time=12 ± 6s).
    assert "Quedamos a eso de las nueve." in stub.calls[0]["context"]

    rows = session.exec(
        select(PhraseAutopsy).where(PhraseAutopsy.video_id == seeded_video.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].phrase_key == "a eso de las nueve"


def test_explain_cache_hit_skips_service(client, session, seeded_video, monkeypatch):
    stub = _stub_explain_returning(VALID_PAYLOAD)
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    # First call populates cache.
    r1 = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "a eso de las nueve", "start_time": 12},
    )
    assert r1.status_code == 200
    assert len(stub.calls) == 1

    # Second call must NOT hit Claude.
    r2 = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "a eso de las nueve", "start_time": 12},
    )
    assert r2.status_code == 200
    assert len(stub.calls) == 1, "service was called twice — cache bypassed"
    assert r2.json()["id"] == r1.json()["id"]


def test_explain_two_casings_hit_one_row(client, session, seeded_video, monkeypatch):
    from models.database import PhraseAutopsy

    stub = _stub_explain_returning(VALID_PAYLOAD)
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    r1 = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "No me da igual", "start_time": 96},
    )
    r2 = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "  no   me da   IGUAL  ", "start_time": 96},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(stub.calls) == 1, "second casing should be a cache hit"
    assert r1.json()["id"] == r2.json()["id"]
    # Original casing of the FIRST insert is preserved for display.
    assert r1.json()["phrase"] == "No me da igual"

    rows = session.exec(
        select(PhraseAutopsy).where(PhraseAutopsy.video_id == seeded_video.id)
    ).all()
    assert len(rows) == 1


def test_explain_empty_phrase_returns_422(client, seeded_video):
    response = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "", "start_time": 10},
    )
    assert response.status_code == 422


def test_explain_long_phrase_returns_422(client, seeded_video):
    response = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "x" * 201, "start_time": 10},
    )
    assert response.status_code == 422


def test_explain_negative_start_time_returns_422(client, seeded_video):
    response = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "frase válida", "start_time": -1},
    )
    assert response.status_code == 422


def test_explain_unknown_video_returns_404(client):
    response = client.post(
        "/api/videos/UNKNOWN_VIDEO/autopsy/explain",
        json={"phrase": "frase", "start_time": 5},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Video no encontrado"


def test_explain_service_failure_returns_502_and_persists_nothing(
    client, session, seeded_video, monkeypatch
):
    from models.database import PhraseAutopsy

    stub = _stub_explain_raises("JSON inválido")
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    response = client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "frase rota", "start_time": 5},
    )
    assert response.status_code == 502
    assert "Generación fallida" in response.json()["detail"]

    rows = session.exec(
        select(PhraseAutopsy).where(PhraseAutopsy.video_id == seeded_video.id)
    ).all()
    assert rows == [], "nothing should be persisted on failure"


def test_explain_falls_back_to_full_transcript_when_no_segments(client, session, monkeypatch):
    """If a video has no segment rows, the route falls back to video.transcript."""
    from models.database import Video

    video = Video(
        youtube_id="LEGACY00000",
        youtube_url="https://youtu.be/LEGACY00000",
        title="legacy",
        duration=60,
        transcript="Transcripción legacy completa.",
    )
    session.add(video)
    session.commit()
    session.refresh(video)

    stub = _stub_explain_returning(VALID_PAYLOAD)
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    response = client.post(
        f"/api/videos/{video.youtube_id}/autopsy/explain",
        json={"phrase": "frase legacy", "start_time": 5},
    )
    assert response.status_code == 200
    assert stub.calls[0]["context"] == ["Transcripción legacy completa."]


def test_list_returns_empty_when_no_rows(client, seeded_video):
    response = client.get(f"/api/videos/{seeded_video.youtube_id}/autopsy")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_all_cached_rows(client, session, seeded_video, monkeypatch):
    stub = _stub_explain_returning(VALID_PAYLOAD)
    monkeypatch.setattr("api.routes.videos.phrase_autopsy_service.explain", stub)

    client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "frase uno", "start_time": 10},
    )
    client.post(
        f"/api/videos/{seeded_video.youtube_id}/autopsy/explain",
        json={"phrase": "frase dos", "start_time": 20},
    )

    response = client.get(f"/api/videos/{seeded_video.youtube_id}/autopsy")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    phrases = {entry["phrase"] for entry in body}
    assert phrases == {"frase uno", "frase dos"}


def test_list_unknown_video_returns_404(client):
    response = client.get("/api/videos/UNKNOWN_VIDEO/autopsy")
    assert response.status_code == 404


def test_unique_constraint_blocks_duplicate_inserts(session, seeded_video):
    """Direct DB insert sanity check: the migration's unique constraint fires."""
    from sqlalchemy.exc import IntegrityError

    from models.database import PhraseAutopsy

    a = PhraseAutopsy(
        video_id=seeded_video.id,
        phrase="frase",
        phrase_key="frase",
        start_time=1.0,
        register="x",
        grammar=json.dumps([{"tag": "t", "text": "x"}]),
        natural_notes=json.dumps(["n"]),
    )
    session.add(a)
    session.commit()

    b = PhraseAutopsy(
        video_id=seeded_video.id,
        phrase="frase otra vez",
        phrase_key="frase",
        start_time=2.0,
        register="y",
        grammar=json.dumps([{"tag": "t", "text": "x"}]),
        natural_notes=json.dumps(["n"]),
    )
    session.add(b)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
