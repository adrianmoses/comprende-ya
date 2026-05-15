"""Tests for `services.chunk_prompts.ChunkPromptsService`.

Mocks the Anthropic client so no real Claude calls happen. Covers parsing,
validation (length + element shape), prompt construction, error mapping.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.chunk_prompts import (
    ChunkPromptsGenerationError,
    chunk_prompts_service,
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
    monkeypatch.setattr(chunk_prompts_service.client, "messages", stub)


VALID_RESPONSE = [
    "Cuéntale a un amigo cuándo sueles cenar usando «a eso de las nueve».",
    "Describe tu rutina matutina mencionando algo que haces «a eso de las nueve».",
    "Invita a alguien a tomar un café «a eso de las nueve».",
]


def test_generate_returns_parsed_prompts(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    out = chunk_prompts_service.generate("a eso de las nueve", ["Quedamos a eso de las nueve."])

    assert out == VALID_RESPONSE


def test_generate_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
    _patch_messages(monkeypatch, _StubMessages(response_text=fenced))

    out = chunk_prompts_service.generate("a eso de las nueve", ["contexto"])
    assert out == VALID_RESPONSE


def test_generate_malformed_json_raises(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(response_text="no es JSON"))
    with pytest.raises(ChunkPromptsGenerationError, match="JSON inválido"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_anthropic_error_wrapped(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(raise_exc=RuntimeError("network")))
    with pytest.raises(ChunkPromptsGenerationError, match="error llamando a Claude"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_object_not_array_raises(monkeypatch):
    # Extractor is lenient (mirrors 017) — it would pull an array out of an
    # object wrapper. To exercise the "not a list" guard we need a payload
    # with no bare-array substring at all.
    _patch_messages(
        monkeypatch,
        _StubMessages(response_text=json.dumps({"foo": "bar"})),
    )
    with pytest.raises(ChunkPromptsGenerationError, match="no es un array"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_non_string_element_raises(monkeypatch):
    _patch_messages(
        monkeypatch,
        _StubMessages(response_text=json.dumps(["consigna válida", 42, "otra consigna"])),
    )
    with pytest.raises(ChunkPromptsGenerationError, match=r"consigna\[1\]"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_empty_array_raises(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(response_text="[]"))
    with pytest.raises(ChunkPromptsGenerationError, match="2-4 consignas"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_single_entry_raises(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(["solo una"])))
    with pytest.raises(ChunkPromptsGenerationError, match="2-4 consignas"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_five_entries_raises(monkeypatch):
    too_many = [f"consigna {i}" for i in range(5)]
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(too_many)))
    with pytest.raises(ChunkPromptsGenerationError, match="2-4 consignas"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_generate_empty_string_entry_raises(monkeypatch):
    _patch_messages(
        monkeypatch,
        _StubMessages(response_text=json.dumps(["válida", "   ", "otra"])),
    )
    with pytest.raises(ChunkPromptsGenerationError, match=r"consigna\[1\]"):
        chunk_prompts_service.generate("frase", ["contexto"])


def test_prompt_includes_phrase_and_context(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    chunk_prompts_service.generate(
        "no me da igual",
        ["Pues fíjate, no me da igual.", "¿Sabes? Yo voy todos los sábados."],
    )

    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "no me da igual" in sent_prompt
    assert "Pues fíjate, no me da igual." in sent_prompt
    assert "¿Sabes? Yo voy todos los sábados." in sent_prompt


def test_prompt_uses_locked_model(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    chunk_prompts_service.generate("frase", ["contexto"])
    assert stub.calls[0]["model"] == "claude-4-sonnet-20250514"


def test_prompt_empty_context_uses_placeholder(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_RESPONSE))
    _patch_messages(monkeypatch, stub)

    chunk_prompts_service.generate("frase", [])

    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "(sin contexto adicional disponible)" in sent_prompt
