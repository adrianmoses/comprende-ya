"""Tests para los endpoints de grabación de chunks (/api/chunks/{id}/recording)."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def recordings_dir(tmp_path, monkeypatch):
    """Apunta RECORDINGS_DIR a un tmp_path para no tocar el directorio real."""
    d = tmp_path / "recordings"
    d.mkdir()
    monkeypatch.setattr("config.settings.RECORDINGS_DIR", str(d))
    return d


@pytest.fixture
def saved_chunk(session, seeded_video):
    """Inserta un chunk guardado sobre el vídeo sembrado."""
    from models.database import Chunk

    chunk = Chunk(
        video_id=seeded_video.id,
        phrase="a eso de las nueve",
        phrase_key="a eso de las nueve",
        start_time=10.0,
        prompts='["Consigna uno.", "Consigna dos."]',
    )
    session.add(chunk)
    session.commit()
    session.refresh(chunk)
    return chunk


def _post(client, chunk_id, data=b"FAKEAUDIO", content_type="audio/webm", **extra):
    files = {"file": ("take.webm", data, content_type)}
    return client.post(f"/api/chunks/{chunk_id}/recording", files=files, data=extra)


def test_post_creates_recording_and_file(client, recordings_dir, saved_chunk):
    res = _post(client, saved_chunk.id, data=b"hello-audio", content_type="audio/webm")
    assert res.status_code == 201
    body = res.json()
    assert body["chunk_id"] == saved_chunk.id
    assert body["content_type"] == "audio/webm"
    assert body["size_bytes"] == len(b"hello-audio")
    # Exactamente un archivo escrito bajo el dir de grabaciones.
    files = list(recordings_dir.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == b"hello-audio"


def test_post_with_duration(client, recordings_dir, saved_chunk):
    res = _post(client, saved_chunk.id, duration_seconds="3.5")
    assert res.status_code == 201
    assert res.json()["duration_seconds"] == 3.5


def test_repost_overwrites_old_file_and_keeps_one_row(client, session, recordings_dir, saved_chunk):
    from sqlmodel import select

    from models.database import Recording

    first = _post(client, saved_chunk.id, data=b"first-take")
    assert first.status_code == 201
    old_files = {f.name for f in recordings_dir.iterdir()}

    second = _post(client, saved_chunk.id, data=b"second-take-longer")
    assert second.status_code == 201

    # El archivo viejo desaparece, queda exactamente uno con el contenido nuevo.
    current = list(recordings_dir.iterdir())
    assert len(current) == 1
    assert current[0].name not in old_files
    assert current[0].read_bytes() == b"second-take-longer"

    # Y una sola fila para el chunk (la unique constraint se respeta).
    rows = session.exec(select(Recording).where(Recording.chunk_id == saved_chunk.id)).all()
    assert len(rows) == 1
    assert rows[0].size_bytes == len(b"second-take-longer")


def test_post_missing_chunk_404_no_file(client, recordings_dir):
    res = _post(client, 99999)
    assert res.status_code == 404
    assert list(recordings_dir.iterdir()) == []


def test_post_over_size_cap_413_no_row_no_file(
    client, session, recordings_dir, saved_chunk, monkeypatch
):
    from sqlmodel import select

    from models.database import Recording

    monkeypatch.setattr("api.routes.chunks.MAX_RECORDING_BYTES", 4)
    res = _post(client, saved_chunk.id, data=b"way-too-big")
    assert res.status_code == 413
    assert list(recordings_dir.iterdir()) == []
    assert session.exec(select(Recording)).all() == []


def test_get_returns_bytes_and_content_type(client, recordings_dir, saved_chunk):
    _post(client, saved_chunk.id, data=b"playback-me", content_type="audio/webm")
    res = client.get(f"/api/chunks/{saved_chunk.id}/recording")
    assert res.status_code == 200
    assert res.content == b"playback-me"
    assert res.headers["content-type"].startswith("audio/webm")


def test_get_is_not_browser_cacheable(client, recordings_dir, saved_chunk):
    # Re-record overwrites at the same URL — the browser must never cache a take,
    # or playback shows a stale recording after reload/re-record.
    _post(client, saved_chunk.id, data=b"playback-me")
    res = client.get(f"/api/chunks/{saved_chunk.id}/recording")
    assert res.headers.get("cache-control") == "no-store"


def test_get_no_recording_404(client, recordings_dir, saved_chunk):
    res = client.get(f"/api/chunks/{saved_chunk.id}/recording")
    assert res.status_code == 404


def test_delete_removes_row_and_file_then_404(client, session, recordings_dir, saved_chunk):
    from sqlmodel import select

    from models.database import Recording

    _post(client, saved_chunk.id, data=b"to-delete")
    assert len(list(recordings_dir.iterdir())) == 1

    res = client.delete(f"/api/chunks/{saved_chunk.id}/recording")
    assert res.status_code == 204
    assert list(recordings_dir.iterdir()) == []
    assert session.exec(select(Recording)).all() == []

    # Segundo delete → 404.
    assert client.delete(f"/api/chunks/{saved_chunk.id}/recording").status_code == 404


def test_list_chunks_has_recording_flag(client, recordings_dir, saved_chunk):
    before = client.get("/api/chunks").json()
    assert before[0]["has_recording"] is False

    _post(client, saved_chunk.id)
    after = client.get("/api/chunks").json()
    assert after[0]["has_recording"] is True


def test_deleting_chunk_cascades_recording_row_and_file(
    client, session, recordings_dir, saved_chunk
):
    from sqlmodel import select

    from models.database import Recording

    _post(client, saved_chunk.id, data=b"orphan-check")
    assert len(list(recordings_dir.iterdir())) == 1

    res = client.delete(f"/api/chunks/{saved_chunk.id}")
    assert res.status_code == 204
    # Ni fila huérfana ni archivo huérfano.
    assert session.exec(select(Recording)).all() == []
    assert list(recordings_dir.iterdir()) == []


def test_stored_path_stays_under_recordings_dir(client, session, recordings_dir, saved_chunk):
    from sqlmodel import select

    from models.database import Recording

    _post(client, saved_chunk.id)
    row = session.exec(select(Recording)).first()
    # La ruta es relativa y el archivo resuelto vive dentro del dir configurado.
    assert not os.path.isabs(row.file_path)
    resolved = os.path.realpath(os.path.join(str(recordings_dir), row.file_path))
    assert resolved.startswith(os.path.realpath(str(recordings_dir)) + os.sep)
