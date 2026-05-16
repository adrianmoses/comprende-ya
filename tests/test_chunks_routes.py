"""Tests for the /api/chunks endpoints."""

from __future__ import annotations

import json

import pytest
from sqlmodel import select

VALID_PROMPTS = [
    "Cuéntale a un amigo cuándo sueles cenar usando «a eso de las nueve».",
    "Describe tu rutina matutina mencionando algo que haces «a eso de las nueve».",
    "Invita a alguien a tomar un café «a eso de las nueve».",
]


@pytest.fixture
def second_video(session):
    """Insert a second video so we can test cross-video listing."""
    from models.database import Video

    video = Video(
        youtube_id="VIDEO2______",
        youtube_url="https://youtu.be/VIDEO2______",
        title="Otro vídeo",
        duration=120,
        transcript="Otro transcripción completa.",
    )
    session.add(video)
    session.commit()
    session.refresh(video)
    return video


def _stub_generate_returning(prompts):
    calls = []

    def _generate(phrase, context):
        calls.append({"phrase": phrase, "context": context})
        return prompts

    _generate.calls = calls
    return _generate


def _stub_generate_raises(message):
    from services.chunk_prompts import ChunkPromptsGenerationError

    calls = []

    def _generate(phrase, context):
        calls.append({"phrase": phrase, "context": context})
        raise ChunkPromptsGenerationError(message)

    _generate.calls = calls
    return _generate


def test_save_cache_miss_calls_service_and_persists(client, session, seeded_video, monkeypatch):
    from models.database import Chunk

    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    response = client.post(
        "/api/chunks",
        json={
            "video_id": seeded_video.youtube_id,
            "phrase": "a eso de las nueve",
            "start_time": 12,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["phrase"] == "a eso de las nueve"
    assert body["video_id"] == seeded_video.youtube_id
    assert body["source_title"] == seeded_video.title
    assert body["prompts"] == VALID_PROMPTS
    assert "id" in body and "created_at" in body

    assert len(stub.calls) == 1
    # Context window includes both seeded segments (start_time=12 ± 6s).
    assert "Quedamos a eso de las nueve." in stub.calls[0]["context"]

    rows = session.exec(select(Chunk).where(Chunk.video_id == seeded_video.id)).all()
    assert len(rows) == 1
    assert rows[0].phrase_key == "a eso de las nueve"


def test_save_cache_hit_skips_service(client, seeded_video, monkeypatch):
    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    r1 = client.post(
        "/api/chunks",
        json={
            "video_id": seeded_video.youtube_id,
            "phrase": "a eso de las nueve",
            "start_time": 12,
        },
    )
    assert r1.status_code == 201
    assert len(stub.calls) == 1

    r2 = client.post(
        "/api/chunks",
        json={
            "video_id": seeded_video.youtube_id,
            "phrase": "a eso de las nueve",
            "start_time": 12,
        },
    )
    assert r2.status_code == 201
    assert len(stub.calls) == 1, "service was called twice — cache bypassed"
    assert r2.json()["id"] == r1.json()["id"]


def test_save_two_casings_hit_one_row(client, session, seeded_video, monkeypatch):
    from models.database import Chunk

    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    r1 = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "No me da igual", "start_time": 96},
    )
    r2 = client.post(
        "/api/chunks",
        json={
            "video_id": seeded_video.youtube_id,
            "phrase": "  no   me da   IGUAL  ",
            "start_time": 96,
        },
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert len(stub.calls) == 1, "second casing should be a cache hit"
    assert r1.json()["id"] == r2.json()["id"]
    # Original casing of the FIRST insert is preserved for display.
    assert r1.json()["phrase"] == "No me da igual"

    rows = session.exec(select(Chunk).where(Chunk.video_id == seeded_video.id)).all()
    assert len(rows) == 1


def test_save_same_phrase_different_videos_creates_two_rows(
    client, session, seeded_video, second_video, monkeypatch
):
    from models.database import Chunk

    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "pues", "start_time": 1},
    )
    client.post(
        "/api/chunks",
        json={"video_id": second_video.youtube_id, "phrase": "pues", "start_time": 1},
    )

    rows = session.exec(select(Chunk)).all()
    assert len(rows) == 2
    assert {r.video_id for r in rows} == {seeded_video.id, second_video.id}
    assert len(stub.calls) == 2  # both are cache misses (different video_id)


def test_save_empty_phrase_returns_422(client, seeded_video):
    response = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "", "start_time": 10},
    )
    assert response.status_code == 422


def test_save_long_phrase_returns_422(client, seeded_video):
    response = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "x" * 201, "start_time": 10},
    )
    assert response.status_code == 422


def test_save_negative_start_time_returns_422(client, seeded_video):
    response = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "frase válida", "start_time": -1},
    )
    assert response.status_code == 422


def test_save_unknown_video_returns_404(client):
    response = client.post(
        "/api/chunks",
        json={"video_id": "UNKNOWN_VIDEO", "phrase": "frase", "start_time": 5},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Video no encontrado"


def test_save_service_failure_returns_502_and_persists_nothing(
    client, session, seeded_video, monkeypatch
):
    from models.database import Chunk

    stub = _stub_generate_raises("JSON inválido")
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    response = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "frase rota", "start_time": 5},
    )
    assert response.status_code == 502
    assert "Generación de consignas fallida" in response.json()["detail"]

    rows = session.exec(select(Chunk).where(Chunk.video_id == seeded_video.id)).all()
    assert rows == [], "nothing should be persisted on failure"


def test_save_falls_back_to_full_transcript_when_no_segments(client, session, monkeypatch):
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

    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    response = client.post(
        "/api/chunks",
        json={"video_id": video.youtube_id, "phrase": "frase legacy", "start_time": 5},
    )
    assert response.status_code == 201
    assert stub.calls[0]["context"] == ["Transcripción legacy completa."]


def test_list_empty_returns_empty_array(client):
    response = client.get("/api/chunks")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_all_rows_newest_first(client, seeded_video, second_video, monkeypatch):
    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "primera", "start_time": 10},
    )
    client.post(
        "/api/chunks",
        json={"video_id": second_video.youtube_id, "phrase": "segunda", "start_time": 20},
    )
    client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "tercera", "start_time": 30},
    )

    response = client.get("/api/chunks")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    # Newest-first: insertion order reversed.
    assert [b["phrase"] for b in body] == ["tercera", "segunda", "primera"]
    # source_title is populated per-row from the joined video.
    by_phrase = {b["phrase"]: b for b in body}
    assert by_phrase["primera"]["source_title"] == seeded_video.title
    assert by_phrase["segunda"]["source_title"] == second_video.title
    assert by_phrase["tercera"]["source_title"] == seeded_video.title


def test_delete_removes_row(client, session, seeded_video, monkeypatch):
    from models.database import Chunk

    stub = _stub_generate_returning(VALID_PROMPTS)
    monkeypatch.setattr("api.routes.chunks.chunk_prompts_service.generate", stub)

    created = client.post(
        "/api/chunks",
        json={"video_id": seeded_video.youtube_id, "phrase": "borrable", "start_time": 1},
    ).json()

    r = client.delete(f"/api/chunks/{created['id']}")
    assert r.status_code == 204

    rows = session.exec(select(Chunk).where(Chunk.video_id == seeded_video.id)).all()
    assert rows == []

    listing = client.get("/api/chunks").json()
    assert [b["id"] for b in listing] == []


def test_delete_unknown_returns_404(client):
    response = client.delete("/api/chunks/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Chunk no encontrado"


def test_unique_constraint_blocks_duplicate_inserts(session, seeded_video):
    """Direct DB insert sanity check: the migration's unique constraint fires."""
    from sqlalchemy.exc import IntegrityError

    from models.database import Chunk

    a = Chunk(
        video_id=seeded_video.id,
        phrase="frase",
        phrase_key="frase",
        start_time=1.0,
        prompts=json.dumps(["a", "b"]),
    )
    session.add(a)
    session.commit()

    b = Chunk(
        video_id=seeded_video.id,
        phrase="otra casing",
        phrase_key="frase",
        start_time=2.0,
        prompts=json.dumps(["c", "d"]),
    )
    session.add(b)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
