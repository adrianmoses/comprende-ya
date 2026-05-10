"""Tokenizador de segmentos para 018.

Función pura: dado el texto de un segmento, una lista de spans (índice + lista
de palabras a localizar) y un modelo spaCy, devuelve la lista de tokens del
segmento (palabras + puntuación) con `span` asignado a los runs contiguos
que coincidan. Si una palabra de un span no aparece de forma contigua en el
segmento, ese span se omite silenciosamente (con un log informativo).

Las claves del dict de cada token siguen el formato del 018:
- `{ "t": "<palabra>" }` — palabra fuera de cualquier span
- `{ "t": "<palabra>", "span": <int>, "start": true }` — primera palabra de un span
- `{ "t": "<palabra>", "span": <int> }` — palabra siguiente dentro del mismo span
- `{ "p": "<puntuación>" }` — puntuación; nunca lleva `span` (no es tappable)
"""

from __future__ import annotations

import logging
import unicodedata

import spacy

logger = logging.getLogger(__name__)


def _normalize_word(word: str) -> str:
    """Casefold + sin diacríticos. Solo para emparejar; el storage conserva el casing."""
    nfkd = unicodedata.normalize("NFKD", word)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return stripped.casefold()


def tokenize_segment(
    text: str,
    span_phrases: list[tuple[int, list[str]]],
    nlp: spacy.Language,
) -> list[dict]:
    """Tokeniza `text` con spaCy y asigna `span` indices a runs contiguos.

    Args:
        text: el `transcript_text` del segmento.
        span_phrases: lista de (span_index, [palabras_del_span]). Las palabras
            son las que vinieron en `tokens_in_segment` del marcador de Claude.
        nlp: instancia de spaCy ya cargada.

    Returns:
        Lista de dicts (uno por token) en el orden original del segmento.
    """

    doc = nlp(text)
    tokens: list[dict] = []
    word_indices: list[int] = []  # posición en `tokens` de cada token-palabra

    for tok in doc:
        if tok.is_space:
            continue
        if tok.is_punct:
            tokens.append({"p": tok.text})
        else:
            word_indices.append(len(tokens))
            tokens.append({"t": tok.text})

    if not span_phrases:
        return tokens

    word_norms = [_normalize_word(tokens[i]["t"]) for i in word_indices]
    occupied: set[int] = set()  # índices en `word_indices` ya tomados por algún span

    for span_index, phrase_words in span_phrases:
        if not phrase_words:
            logger.debug("Saltando span %s: lista de palabras vacía", span_index)
            continue
        target = [_normalize_word(w) for w in phrase_words]
        n = len(target)
        match_start: int | None = None
        for i in range(0, len(word_norms) - n + 1):
            if any((i + k) in occupied for k in range(n)):
                continue
            if word_norms[i : i + n] == target:
                match_start = i
                break
        if match_start is None:
            logger.info(
                "Saltando span %s: no se encontró '%s' contiguo en el segmento",
                span_index,
                " ".join(phrase_words),
            )
            continue
        for k in range(n):
            position_in_tokens = word_indices[match_start + k]
            tokens[position_in_tokens]["span"] = span_index
            if k == 0:
                tokens[position_in_tokens]["start"] = True
            occupied.add(match_start + k)

    return tokens
