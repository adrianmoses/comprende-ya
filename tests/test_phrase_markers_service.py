"""Tests for `services.phrase_markers.PhraseMarkersService`.

Mocks the Anthropic client so no real Claude calls happen. Covers parsing,
per-entry validation (invalid entries dropped, not fatal), prompt construction,
and error mapping.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from models.database import VideoSegment
from services.phrase_markers import (
    PhraseMarkersGenerationError,
    phrase_markers_service,
)


def _fake_message(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


class _StubMessages:
    def __init__(self, response_text: str | None = None, raise_exc: Exception | None = None):
        self.response_text = response_text
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc:
            raise self.raise_exc
        return _fake_message(self.response_text or "")


def _patch_messages(monkeypatch, stub: _StubMessages):
    monkeypatch.setattr(phrase_markers_service.client, "messages", stub)


def _segments(*pairs: tuple[int, float, str]) -> list[VideoSegment]:
    return [
        VideoSegment(
            video_id=1,
            segment_number=n,
            transcript_text=text,
            start_time=t,
            end_time=t + 5.0,
        )
        for n, t, text in pairs
    ]


def _valid_marker(phrase: str = "no me da igual", segment_number: int = 0):
    return {
        "phrase": phrase,
        "segment_number": segment_number,
        "tokens_in_segment": phrase.split(),
        "register": "coloquial · enfático",
        "grammar": [
            {"tag": "negación", "text": "«no» niega el verbo principal."},
            {"tag": "verbo impersonal", "text": "«da igual» se construye con sujeto fijo."},
        ],
        "natural_notes": [
            "Suena a réplica viva, no neutra.",
            "Más cálido que «me importa».",
        ],
    }


VALID_RESPONSE = {"markers": [_valid_marker()]}


def test_explain_video_returns_parsed_markers(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    out = phrase_markers_service.explain_video(_segments((0, 0.0, "no me da igual.")))

    assert len(out) == 1
    m = out[0]
    assert m["phrase"] == "no me da igual"
    assert m["segment_number"] == 0
    assert m["tokens_in_segment"] == ["no", "me", "da", "igual"]
    assert m["register"] == "coloquial · enfático"
    assert len(m["grammar"]) == 2
    assert m["grammar"][0] == {"tag": "negación", "text": "«no» niega el verbo principal."}
    assert len(m["natural_notes"]) == 2


def test_explain_video_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
    stub = _StubMessages(response_text=fenced)
    _patch_messages(monkeypatch, stub)

    out = phrase_markers_service.explain_video(_segments((0, 0.0, "no me da igual.")))
    assert len(out) == 1


def test_explain_video_malformed_json_raises(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(response_text="no es JSON"))
    with pytest.raises(PhraseMarkersGenerationError, match="JSON inválido"):
        phrase_markers_service.explain_video(_segments((0, 0.0, "x")))


def test_explain_video_anthropic_error_wrapped(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(raise_exc=RuntimeError("network")))
    with pytest.raises(PhraseMarkersGenerationError, match="error llamando a Claude"):
        phrase_markers_service.explain_video(_segments((0, 0.0, "x")))


def test_explain_video_drops_invalid_entry_keeps_valid(monkeypatch):
    bad = _valid_marker()
    bad["grammar"] = []  # invalid: empty grammar
    response = {"markers": [bad, _valid_marker(phrase="vale, vale")]}
    stub = _StubMessages(response_text=json.dumps(response))
    _patch_messages(monkeypatch, stub)

    out = phrase_markers_service.explain_video(_segments((0, 0.0, "x")))
    assert len(out) == 1
    assert out[0]["phrase"] == "vale, vale"


def test_explain_video_all_invalid_raises(monkeypatch):
    bad = _valid_marker()
    bad["register"] = ""
    response = {"markers": [bad]}
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(response)))
    with pytest.raises(PhraseMarkersGenerationError, match="ningún marcador válido"):
        phrase_markers_service.explain_video(_segments((0, 0.0, "x")))


def test_explain_video_missing_markers_key_raises(monkeypatch):
    response = {"foo": []}
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(response)))
    with pytest.raises(PhraseMarkersGenerationError, match="markers"):
        phrase_markers_service.explain_video(_segments((0, 0.0, "x")))


def test_prompt_includes_every_segment_with_number_and_start_time(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    phrase_markers_service.explain_video(
        _segments(
            (0, 0.0, "Hola, qué tal."),
            (1, 4.5, "Pues mira, no me da igual."),
            (2, 9.2, "Pero bueno, sigamos."),
        )
    )

    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "[0 | 0.0s] Hola, qué tal." in sent_prompt
    assert "[1 | 4.5s] Pues mira, no me da igual." in sent_prompt
    assert "[2 | 9.2s] Pero bueno, sigamos." in sent_prompt


def test_prompt_uses_locked_model(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    phrase_markers_service.explain_video(_segments((0, 0.0, "x")))
    assert stub.calls[0]["model"] == "claude-sonnet-4-6"


def test_prompt_mentions_marker_bounds(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    phrase_markers_service.explain_video(_segments((0, 0.0, "x")))
    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "5" in sent_prompt and "15" in sent_prompt
