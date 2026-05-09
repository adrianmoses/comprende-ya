"""Servicio que pide a Claude una autopsia (en español) de una frase concreta.

El servicio no sabe nada de caché ni de la base de datos: recibe la frase y un
contexto opcional, devuelve un payload tipado, lanza `AutopsyGenerationError`
si Claude falla o devuelve algo que no parsea.
"""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

from config import settings
from repositories.autopsy_repository import AutopsyPayload

MODEL = "claude-4-sonnet-20250514"
MAX_TOKENS = 1200

_PROMPT_TEMPLATE = """\
Eres un lingüista hispanohablante explicándole a una estudiante de español de
nivel B2 (Ana) por qué cierta frase de un vídeo le sonó natural pero no la pudo
analizar. Toda tu respuesta es en español. NO traduzcas al inglés. NO incluyas
campos de traducción ni "literal".

Devuelve EXCLUSIVAMENTE un JSON con esta forma exacta:

{{
  "register": string,        // p. ej. "cotidiano · neutral", "formal · escrito", "coloquial · enfático"
  "grammar": [               // entre 2 y 5 entradas
    {{ "tag": string, "text": string }}
  ],
  "natural_notes": [string]  // entre 2 y 4 observaciones cortas en español
}}

Reglas:
- Cada `tag` es una etiqueta gramatical breve en español (preferiblemente
  ≤25 caracteres, máximo 40): «preposición», «subjuntivo de duda»,
  «pronombre dativo», «verbo impersonal», «discurso indirecto», etc. No
  repitas la misma etiqueta dos veces.
- Cada `text` es UNA sola frase en español que explica el papel de ese elemento
  en *esta* frase concreta — no una definición de manual.
- Cada `natural_notes` es una observación corta en español sobre por qué suena
  nativo, qué registro evoca, qué alternativa habría sido más rígida o menos
  idiomática, o cuándo NO lo dirías. Escribe a una persona B2: nada de jerga
  lingüística pesada, nada de tautologías («es natural porque suena natural»).
- No envuelvas el JSON en markdown. No añadas comentarios ni texto fuera del
  objeto JSON.

Frase a analizar:
«{phrase}»

Contexto inmediato del vídeo (segmentos cercanos, en orden):
{context_block}
"""


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.MULTILINE)
_BARE_OBJECT_RE = re.compile(r'(\{\s*"[\s\S]*\})')


class AutopsyGenerationError(Exception):
    """Claude devolvió algo no parseable o la llamada falló."""


def _extract_json(text: str) -> str:
    text = text.strip()
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate
    bare = _BARE_OBJECT_RE.search(text)
    if bare:
        return bare.group(1).strip()
    return text


def _build_prompt(phrase: str, context_segments: list[str]) -> str:
    if context_segments:
        context_block = "\n".join(f"- {seg.strip()}" for seg in context_segments)
    else:
        context_block = "- (sin contexto adicional disponible)"
    return _PROMPT_TEMPLATE.format(phrase=phrase, context_block=context_block)


def _validate_payload(data: object) -> AutopsyPayload:
    if not isinstance(data, dict):
        raise AutopsyGenerationError("la respuesta de Claude no es un objeto JSON")

    register = data.get("register")
    if not isinstance(register, str) or not register.strip():
        raise AutopsyGenerationError("falta o es inválido el campo 'register'")

    grammar = data.get("grammar")
    if not isinstance(grammar, list) or not grammar:
        raise AutopsyGenerationError("falta o es inválido el campo 'grammar'")
    for i, row in enumerate(grammar):
        if not isinstance(row, dict):
            raise AutopsyGenerationError(f"grammar[{i}] no es un objeto")
        tag = row.get("tag")
        text_value = row.get("text")
        if not isinstance(tag, str) or not tag.strip():
            raise AutopsyGenerationError(f"grammar[{i}].tag inválido")
        if not isinstance(text_value, str) or not text_value.strip():
            raise AutopsyGenerationError(f"grammar[{i}].text inválido")

    notes = data.get("natural_notes")
    if not isinstance(notes, list) or not notes:
        raise AutopsyGenerationError("falta o es inválido el campo 'natural_notes'")
    for i, note in enumerate(notes):
        if not isinstance(note, str) or not note.strip():
            raise AutopsyGenerationError(f"natural_notes[{i}] inválido")

    return AutopsyPayload(
        register=register,
        grammar=[{"tag": r["tag"], "text": r["text"]} for r in grammar],
        natural_notes=list(notes),
    )


class PhraseAutopsyService:
    def __init__(self) -> None:
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def explain(self, phrase: str, context_segments: list[str]) -> AutopsyPayload:
        prompt = _build_prompt(phrase, context_segments)
        try:
            message = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - red de seguridad para errores de SDK / red
            raise AutopsyGenerationError(f"error llamando a Claude: {exc}") from exc

        try:
            raw = message.content[0].text
        except (AttributeError, IndexError) as exc:
            raise AutopsyGenerationError("respuesta de Claude vacía o inesperada") from exc

        json_text = _extract_json(raw)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise AutopsyGenerationError(f"Claude devolvió JSON inválido: {exc}") from exc

        return _validate_payload(parsed)


phrase_autopsy_service = PhraseAutopsyService()
