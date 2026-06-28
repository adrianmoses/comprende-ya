"""Servicio que pide a Claude marcadores de frases interesantes para todo un vídeo.

El servicio recibe la lista de segmentos del vídeo, le pasa la transcripción
completa a Claude (numerada por segmentos, con `start_time`) y le pide que
escoja entre 5 y 15 frases dignas de "tap" para una estudiante B2: modismos,
frases con registro marcado, puntos de presión gramatical. Para cada frase
también devuelve el payload de autopsia con el mismo esquema que
`services/phrase_autopsy.py` para poder pre-poblar la caché de 017.

Este servicio no toca la base de datos ni la caché: recibe segmentos y devuelve
`list[MarkerEntry]`. Lanza `PhraseMarkersGenerationError` si la llamada o el
parseo fallan por completo. Entradas individuales mal formadas se descartan
(se loguean) sin abortar el batch.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypedDict

from anthropic import Anthropic

from config import settings
from models.database import VideoSegment

MODEL = settings.CLAUDE_MODEL
MAX_TOKENS = 4000
MIN_MARKERS = 5
MAX_MARKERS = 15

logger = logging.getLogger(__name__)


class MarkerEntry(TypedDict):
    phrase: str
    segment_number: int
    tokens_in_segment: list[str]
    register: str
    grammar: list[dict]
    natural_notes: list[str]


_PROMPT_TEMPLATE = """\
Eres un lingüista hispanohablante leyendo la transcripción completa de un
vídeo en español. Tu tarea es identificar entre {min_markers} y {max_markers}
frases — modismos, expresiones con registro marcado, puntos de presión
gramatical — que merecen una pausa para una estudiante de nivel B2 (Ana).
Después, para cada frase, produces su autopsia.

Toda tu respuesta es en español. NO traduzcas al inglés. NO incluyas campos
de traducción ni "literal".

La transcripción está numerada por segmentos. Cada segmento empieza con
«[N | start_time s]» seguido del texto del segmento.

Devuelve EXCLUSIVAMENTE un JSON con esta forma exacta:

{{
  "markers": [
    {{
      "phrase": string,                      // la frase tal y como aparece en el segmento
      "segment_number": int,                 // número del segmento donde vive la frase
      "tokens_in_segment": [string, ...],    // palabras de la frase en orden, sin puntuación
      "register": string,                    // p. ej. "cotidiano · neutral"
      "grammar": [                            // entre 2 y 5 entradas
        {{ "tag": string, "text": string }}
      ],
      "natural_notes": [string]              // entre 2 y 4 observaciones cortas
    }}
  ]
}}

Reglas para `markers`:
- Entre {min_markers} y {max_markers} entradas en total.
- Cada `phrase` debe vivir COMPLETAMENTE dentro de un solo segmento (no atravieses
  fronteras de segmento).
- `tokens_in_segment` son las palabras de la frase EN ORDEN, sin puntuación —
  exactamente las palabras que aparecen en el segmento `segment_number`.
- Una frase puede tener entre 1 y 6 palabras; prefiere frases multipalabra.
- No repitas la misma frase dos veces.

Reglas para la autopsia (cada entrada):
- Cada `tag` es una etiqueta gramatical breve en español (preferiblemente
  ≤25 caracteres, máximo 40): «preposición», «subjuntivo de duda»,
  «pronombre dativo», «verbo impersonal», «discurso indirecto», etc. No
  repitas la misma etiqueta dos veces dentro de la misma autopsia.
- Cada `text` es UNA sola frase en español que explica el papel de ese elemento
  en *esta* frase concreta — no una definición de manual.
- Cada `natural_notes` es una observación corta en español sobre por qué suena
  nativo, qué registro evoca, qué alternativa habría sido más rígida o menos
  idiomática, o cuándo NO lo dirías. Escribe a una persona B2: nada de jerga
  lingüística pesada, nada de tautologías («es natural porque suena natural»).
- No envuelvas el JSON en markdown. No añadas comentarios ni texto fuera del
  objeto JSON.

Transcripción:
{transcript_block}
"""

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.MULTILINE)
_BARE_OBJECT_RE = re.compile(r'(\{\s*"[\s\S]*\})')


class PhraseMarkersGenerationError(Exception):
    """Claude devolvió algo no parseable o la llamada falló por completo."""


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


def _build_transcript_block(segments: list[VideoSegment]) -> str:
    return "\n".join(
        f"[{seg.segment_number} | {seg.start_time:.1f}s] {seg.transcript_text}" for seg in segments
    )


def _build_prompt(segments: list[VideoSegment]) -> str:
    return _PROMPT_TEMPLATE.format(
        min_markers=MIN_MARKERS,
        max_markers=MAX_MARKERS,
        transcript_block=_build_transcript_block(segments),
    )


class _MarkerEntryInvalid(Exception):
    """Una sola entrada de marcador no pasó la validación."""


def _validate_marker(entry: object) -> MarkerEntry:
    if not isinstance(entry, dict):
        raise _MarkerEntryInvalid("la entrada no es un objeto JSON")

    phrase = entry.get("phrase")
    if not isinstance(phrase, str) or not phrase.strip():
        raise _MarkerEntryInvalid("phrase inválido o ausente")

    segment_number = entry.get("segment_number")
    if not isinstance(segment_number, int) or isinstance(segment_number, bool):
        raise _MarkerEntryInvalid("segment_number debe ser entero")

    tokens_in_segment = entry.get("tokens_in_segment")
    if not isinstance(tokens_in_segment, list) or not tokens_in_segment:
        raise _MarkerEntryInvalid("tokens_in_segment inválido o vacío")
    for i, tok in enumerate(tokens_in_segment):
        if not isinstance(tok, str) or not tok.strip():
            raise _MarkerEntryInvalid(f"tokens_in_segment[{i}] inválido")

    register = entry.get("register")
    if not isinstance(register, str) or not register.strip():
        raise _MarkerEntryInvalid("register inválido o ausente")

    grammar = entry.get("grammar")
    if not isinstance(grammar, list) or not grammar:
        raise _MarkerEntryInvalid("grammar inválido o vacío")
    grammar_clean: list[dict] = []
    for i, row in enumerate(grammar):
        if not isinstance(row, dict):
            raise _MarkerEntryInvalid(f"grammar[{i}] no es un objeto")
        tag = row.get("tag")
        text_value = row.get("text")
        if not isinstance(tag, str) or not tag.strip():
            raise _MarkerEntryInvalid(f"grammar[{i}].tag inválido")
        if not isinstance(text_value, str) or not text_value.strip():
            raise _MarkerEntryInvalid(f"grammar[{i}].text inválido")
        grammar_clean.append({"tag": tag, "text": text_value})

    notes = entry.get("natural_notes")
    if not isinstance(notes, list) or not notes:
        raise _MarkerEntryInvalid("natural_notes inválido o vacío")
    for i, note in enumerate(notes):
        if not isinstance(note, str) or not note.strip():
            raise _MarkerEntryInvalid(f"natural_notes[{i}] inválido")

    return MarkerEntry(
        phrase=phrase.strip(),
        segment_number=segment_number,
        tokens_in_segment=[t.strip() for t in tokens_in_segment],
        register=register,
        grammar=grammar_clean,
        natural_notes=list(notes),
    )


class PhraseMarkersService:
    def __init__(self) -> None:
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def explain_video(self, segments: list[VideoSegment]) -> list[MarkerEntry]:
        prompt = _build_prompt(segments)
        try:
            message = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - red de seguridad para errores de SDK / red
            raise PhraseMarkersGenerationError(f"error llamando a Claude: {exc}") from exc

        try:
            raw = message.content[0].text
        except (AttributeError, IndexError) as exc:
            raise PhraseMarkersGenerationError("respuesta de Claude vacía o inesperada") from exc

        json_text = _extract_json(raw)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise PhraseMarkersGenerationError(f"Claude devolvió JSON inválido: {exc}") from exc

        if not isinstance(parsed, dict):
            raise PhraseMarkersGenerationError("la respuesta no es un objeto JSON")
        markers = parsed.get("markers")
        if not isinstance(markers, list):
            raise PhraseMarkersGenerationError("la respuesta no contiene 'markers' como lista")

        result: list[MarkerEntry] = []
        for i, raw_entry in enumerate(markers):
            try:
                result.append(_validate_marker(raw_entry))
            except _MarkerEntryInvalid as exc:
                logger.warning("Saltando marcador %s: %s", i, exc)
                continue

        if not result:
            raise PhraseMarkersGenerationError("ningún marcador válido tras la validación")

        return result


phrase_markers_service = PhraseMarkersService()
