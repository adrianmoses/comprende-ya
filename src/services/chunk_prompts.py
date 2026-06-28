"""Servicio que pide a Claude consignas de uso (en español) para una frase guardada.

El servicio no sabe nada de caché ni de la base de datos: recibe la frase y su
contexto inmediato, devuelve una lista de 2-4 consignas, lanza
`ChunkPromptsGenerationError` si Claude falla o devuelve algo que no parsea.
"""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

from config import settings

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1200

_PROMPT_TEMPLATE = """\
Eres un profesor de español enseñando a Ana (B2) a *usar* una expresión que
acaba de guardar de un vídeo. Te paso la frase y el contexto inmediato donde
la oyó.

Devuelve EXCLUSIVAMENTE un JSON: un array de 2 a 4 cadenas en español. Cada
cadena es UNA sola consigna corta (1-2 frases) que invita a Ana a usar la
frase «{phrase}» en una situación NUEVA — nunca a traducirla, definirla ni
analizarla.

Reglas:
- La frase «{phrase}» aparece explícitamente en cada consigna como objetivo
  a usar. Puede ir entre comillas o integrada en la consigna como ejemplo.
- Mezcla registros y escenarios: al menos una consigna social/conversacional
  (hablar con alguien) y al menos una reflexiva/personal (contar algo tuyo).
- Sin metalingüística: NO escribas «qué significa», «cuándo se usa», «explica»,
  «traduce», «define».
- Español únicamente. No incluyas inglés en ninguna consigna.
- Solo el array JSON. Sin markdown, sin comentarios, sin texto fuera del JSON.

Frase: «{phrase}»
Contexto inmediato del vídeo:
{context_block}
"""


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.MULTILINE)
_BARE_ARRAY_RE = re.compile(r"(\[[\s\S]*\])")


class ChunkPromptsGenerationError(Exception):
    """Claude devolvió algo no parseable o la llamada falló."""


def _extract_json(text: str) -> str:
    text = text.strip()
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate.startswith("[") or candidate.startswith("{"):
            return candidate
    bare = _BARE_ARRAY_RE.search(text)
    if bare:
        return bare.group(1).strip()
    return text


def _build_prompt(phrase: str, context_segments: list[str]) -> str:
    if context_segments:
        context_block = "\n".join(f"- {seg.strip()}" for seg in context_segments)
    else:
        context_block = "- (sin contexto adicional disponible)"
    return _PROMPT_TEMPLATE.format(phrase=phrase, context_block=context_block)


def _validate(data: object) -> list[str]:
    if not isinstance(data, list):
        raise ChunkPromptsGenerationError("la respuesta de Claude no es un array JSON")
    if not (2 <= len(data) <= 4):
        raise ChunkPromptsGenerationError(f"se esperaban 2-4 consignas; vinieron {len(data)}")
    out: list[str] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, str) or not entry.strip():
            raise ChunkPromptsGenerationError(f"consigna[{i}] inválida (no es str o está vacía)")
        out.append(entry.strip())
    return out


class ChunkPromptsService:
    def __init__(self) -> None:
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate(self, phrase: str, context_segments: list[str]) -> list[str]:
        prompt = _build_prompt(phrase, context_segments)
        try:
            message = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - red de seguridad para errores de SDK / red
            raise ChunkPromptsGenerationError(f"error llamando a Claude: {exc}") from exc

        try:
            raw = message.content[0].text
        except (AttributeError, IndexError) as exc:
            raise ChunkPromptsGenerationError("respuesta de Claude vacía o inesperada") from exc

        json_text = _extract_json(raw)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ChunkPromptsGenerationError(f"Claude devolvió JSON inválido: {exc}") from exc

        return _validate(parsed)


chunk_prompts_service = ChunkPromptsService()
