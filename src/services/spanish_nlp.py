"""Carga compartida del modelo spaCy en español (`es_dep_news_trf`).

Tanto el generador de ejercicios (007) como el tokenizador de segmentos (018)
usan el mismo modelo. Cargarlo dos veces consume memoria sin beneficio, así
que este módulo expone una instancia compartida cargada bajo demanda.
"""

from __future__ import annotations

from threading import Lock
from typing import Optional

import spacy

_NLP: Optional[spacy.Language] = None
_LOCK = Lock()


def get_nlp() -> spacy.Language:
    """Carga (la primera vez) y devuelve la instancia compartida de spaCy."""
    global _NLP
    if _NLP is not None:
        return _NLP
    with _LOCK:
        if _NLP is None:
            spacy.prefer_gpu()
            _NLP = spacy.load("es_dep_news_trf")
    return _NLP
