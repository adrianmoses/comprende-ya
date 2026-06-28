"""Tests for GET /api/videos/search — error mapping (031).

The happy path hits the live YouTube Data API, so it isn't exercised here; these
cover the route's input guard and the YoutubeSearchError → 503 mapping (the 031
hardening) with the service stubbed.
"""

from __future__ import annotations

from services.youtube_search import YoutubeSearchError


def test_empty_query_is_400(client):
    response = client.get("/api/videos/search?query=%20%20")
    assert response.status_code == 400, response.text


def test_youtube_error_maps_to_503(client, monkeypatch):
    def _boom(query, max_results):
        raise YoutubeSearchError("quotaExceeded")

    monkeypatch.setattr("api.routes.videos.youtube_search.search_videos", _boom)

    response = client.get("/api/videos/search?query=español")
    assert response.status_code == 503, response.text
    assert "no disponible" in response.json()["detail"].lower()


def test_results_passed_through(client, monkeypatch):
    fake = [{"video_id": "abc123", "title": "Prueba", "duration": 120}]
    monkeypatch.setattr(
        "api.routes.videos.youtube_search.search_videos",
        lambda query, max_results: fake,
    )

    response = client.get("/api/videos/search?query=español&max_results=12")
    assert response.status_code == 200, response.text
    assert response.json() == {"results": fake}
