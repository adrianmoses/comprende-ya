"""Tests for `services.phrase_autopsy.PhraseAutopsyService`.

Mocks the Anthropic client so no real Claude calls happen. Covers parsing,
validation, prompt construction, and error mapping.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.phrase_autopsy import (
    AutopsyGenerationError,
    PhraseAutopsyService,
    phrase_autopsy_service,
)


def _fake_message(text: str):
    """Mimic an anthropic Message object: `.content[0].text` access."""
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
    """Swap the singleton's client.messages so we don't hit the network."""
    monkeypatch.setattr(phrase_autopsy_service.client, "messages", stub)


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


def test_explain_returns_parsed_payload(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_PAYLOAD))
    _patch_messages(monkeypatch, stub)

    out = phrase_autopsy_service.explain(
        "a eso de las nueve",
        ["Quedamos a eso de las nueve.", "Yo creo que para entonces ya habré salido."],
    )

    assert out["register"] == "cotidiano · neutral"
    assert len(out["grammar"]) == 2
    assert out["grammar"][0] == {"tag": "preposición", "text": "«a» marca la hora puntual."}
    assert out["natural_notes"] == VALID_PAYLOAD["natural_notes"]


def test_explain_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{json.dumps(VALID_PAYLOAD)}\n```"
    stub = _StubMessages(response_text=fenced)
    _patch_messages(monkeypatch, stub)

    out = phrase_autopsy_service.explain("frase", ["contexto"])
    assert out["register"] == "cotidiano · neutral"


def test_explain_malformed_json_raises(monkeypatch):
    _patch_messages(monkeypatch, _StubMessages(response_text="not json at all"))
    with pytest.raises(AutopsyGenerationError, match="JSON inválido"):
        phrase_autopsy_service.explain("frase", ["contexto"])


def test_explain_missing_register_raises(monkeypatch):
    bad = {"grammar": VALID_PAYLOAD["grammar"], "natural_notes": VALID_PAYLOAD["natural_notes"]}
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(bad)))
    with pytest.raises(AutopsyGenerationError, match="register"):
        phrase_autopsy_service.explain("frase", ["contexto"])


def test_explain_empty_grammar_raises(monkeypatch):
    bad = {**VALID_PAYLOAD, "grammar": []}
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(bad)))
    with pytest.raises(AutopsyGenerationError, match="grammar"):
        phrase_autopsy_service.explain("frase", ["contexto"])


def test_explain_grammar_row_missing_text_raises(monkeypatch):
    bad = {**VALID_PAYLOAD, "grammar": [{"tag": "preposición"}]}
    _patch_messages(monkeypatch, _StubMessages(response_text=json.dumps(bad)))
    with pytest.raises(AutopsyGenerationError, match=r"grammar\[0\]\.text"):
        phrase_autopsy_service.explain("frase", ["contexto"])


def test_explain_anthropic_error_wrapped(monkeypatch):
    _patch_messages(
        monkeypatch,
        _StubMessages(raise_exc=RuntimeError("network down")),
    )
    with pytest.raises(AutopsyGenerationError, match="error llamando a Claude"):
        phrase_autopsy_service.explain("frase", ["contexto"])


def test_prompt_includes_phrase_and_context_verbatim(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_PAYLOAD))
    _patch_messages(monkeypatch, stub)

    phrase_autopsy_service.explain(
        "no me da igual",
        ["Mira, dilo como quieras, pero no me da igual.", "Llevamos meses con lo mismo."],
    )

    assert len(stub.calls) == 1
    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "no me da igual" in sent_prompt
    assert "Mira, dilo como quieras" in sent_prompt
    assert "Llevamos meses" in sent_prompt


def test_prompt_handles_empty_context(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_PAYLOAD))
    _patch_messages(monkeypatch, stub)

    phrase_autopsy_service.explain("frase suelta", [])

    sent_prompt = stub.calls[0]["messages"][0]["content"]
    assert "frase suelta" in sent_prompt
    assert "sin contexto adicional" in sent_prompt


def test_singleton_uses_locked_model(monkeypatch):
    stub = _StubMessages(response_text=json.dumps(VALID_PAYLOAD))
    _patch_messages(monkeypatch, stub)

    phrase_autopsy_service.explain("frase", ["x"])

    assert stub.calls[0]["model"] == "claude-sonnet-4-6"


def test_construct_service_directly():
    """Sanity check that PhraseAutopsyService can be instantiated standalone."""
    svc = PhraseAutopsyService()
    assert svc.client is not None
