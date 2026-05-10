"""Tests for `services.segment_tokenizer.tokenize_segment`.

Uses `spacy.blank("es")` so tests don't need the transformer model loaded.
The tokeniser only relies on `is_punct` / `is_space` / `text` from spaCy,
so the blank Spanish pipeline is sufficient.
"""

from __future__ import annotations

import pytest
import spacy

from services.segment_tokenizer import tokenize_segment


@pytest.fixture(scope="module")
def nlp():
    return spacy.blank("es")


def test_no_spans_returns_plain_word_and_punct_tokens(nlp):
    out = tokenize_segment("Mira, no me da igual.", [], nlp)
    assert out == [
        {"t": "Mira"},
        {"p": ","},
        {"t": "no"},
        {"t": "me"},
        {"t": "da"},
        {"t": "igual"},
        {"p": "."},
    ]


def test_single_span_marks_first_word_with_start(nlp):
    out = tokenize_segment(
        "Mira, no me da igual.",
        [(0, ["no", "me", "da", "igual"])],
        nlp,
    )
    assert out == [
        {"t": "Mira"},
        {"p": ","},
        {"t": "no", "span": 0, "start": True},
        {"t": "me", "span": 0},
        {"t": "da", "span": 0},
        {"t": "igual", "span": 0},
        {"p": "."},
    ]


def test_two_spans_get_distinct_indices(nlp):
    out = tokenize_segment(
        "A ver, dilo como quieras, pero no me da igual.",
        [(0, ["dilo", "como", "quieras"]), (1, ["no", "me", "da", "igual"])],
        nlp,
    )

    starts = [(i, t) for i, t in enumerate(out) if t.get("start")]
    assert len(starts) == 2
    span_0_words = [t["t"] for t in out if t.get("span") == 0]
    span_1_words = [t["t"] for t in out if t.get("span") == 1]
    assert span_0_words == ["dilo", "como", "quieras"]
    assert span_1_words == ["no", "me", "da", "igual"]


def test_phrase_not_in_segment_is_silently_dropped(nlp):
    out = tokenize_segment(
        "Hola, qué tal estás.",
        [(0, ["no", "me", "da", "igual"])],
        nlp,
    )
    assert all("span" not in t for t in out)
    text_chunks = [t.get("t", t.get("p")) for t in out]
    assert "Hola" in text_chunks


def test_non_contiguous_phrase_is_dropped_other_tokens_still_populated(nlp):
    out = tokenize_segment(
        "Yo no creo que me importe igual.",
        [
            (0, ["no", "me", "da", "igual"]),  # not contiguous: "da" missing between
            (1, ["no", "creo"]),  # this one IS contiguous
        ],
        nlp,
    )

    # span 0 dropped
    assert all(t.get("span") != 0 for t in out)
    # span 1 present
    span_1 = [t["t"] for t in out if t.get("span") == 1]
    assert span_1 == ["no", "creo"]


def test_punctuation_heavy_text_preserves_punctuation(nlp):
    out = tokenize_segment("¡Vamos! ¿Lo viste? Sí…", [], nlp)
    types = [next(iter(t.keys())) for t in out]
    assert "p" in types
    # Joining the values should reconstruct (close to) the original.
    rendered = "".join(t.get("t", t.get("p", "")) for t in out)
    for ch in ["¡", "!", "¿", "?"]:
        assert ch in rendered


def test_match_is_case_and_accent_insensitive(nlp):
    out = tokenize_segment(
        "Está dificilísimo.",
        [(0, ["está", "dificilisimo"])],
        nlp,
    )
    span_words = [t["t"] for t in out if t.get("span") == 0]
    assert span_words == ["Está", "dificilísimo"]


def test_two_overlapping_spans_second_dropped(nlp):
    out = tokenize_segment(
        "Pero no me da igual.",
        [(0, ["no", "me", "da"]), (1, ["me", "da", "igual"])],
        nlp,
    )
    # The first span occupies positions; the second overlaps and must be dropped.
    span_0 = [t["t"] for t in out if t.get("span") == 0]
    span_1 = [t for t in out if t.get("span") == 1]
    assert span_0 == ["no", "me", "da"]
    assert span_1 == []


def test_first_word_only_has_start(nlp):
    out = tokenize_segment(
        "no me da igual",
        [(0, ["no", "me", "da", "igual"])],
        nlp,
    )
    starts = [t for t in out if t.get("start")]
    assert len(starts) == 1
    assert starts[0]["t"] == "no"


def test_empty_text_returns_empty(nlp):
    out = tokenize_segment("", [], nlp)
    assert out == []


def test_single_word_span(nlp):
    out = tokenize_segment("Eso es flipante.", [(0, ["flipante"])], nlp)
    span_words = [t["t"] for t in out if t.get("span") == 0]
    assert span_words == ["flipante"]
    starts = [t for t in out if t.get("start")]
    assert len(starts) == 1
