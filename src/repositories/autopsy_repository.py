"""Repositorio para `phrase_autopsy` — caché por (video_id, phrase_key)."""

from __future__ import annotations

import json
import re
from typing import List, Optional, TypedDict

from sqlmodel import Session, select

from models.database import PhraseAutopsy
from models.schemas import AutopsyEntryResponse, AutopsyGrammarRow

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_phrase(phrase: str) -> str:
    """Normaliza una frase para usarla como clave de caché.

    Trim → colapsa espacios internos → casefold. Sin quitar acentos ni
    puntuación: «no me da igual» y «No  me da igual.» comparten clave;
    «no me da igual» y «no, me da igual» no.
    """
    return _WHITESPACE_RE.sub(" ", phrase.strip()).casefold()


class AutopsyPayload(TypedDict):
    """Forma del payload parseado que devuelve `PhraseAutopsyService.explain`."""

    register: str
    grammar: list[dict]
    natural_notes: list[str]


class AutopsyRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_phrase(self, video_id: int, phrase_key: str) -> Optional[PhraseAutopsy]:
        statement = select(PhraseAutopsy).where(
            PhraseAutopsy.video_id == video_id,
            PhraseAutopsy.phrase_key == phrase_key,
        )
        return self.session.exec(statement).first()

    def list_for_video(self, video_id: int) -> List[PhraseAutopsy]:
        statement = (
            select(PhraseAutopsy)
            .where(PhraseAutopsy.video_id == video_id)
            .order_by(PhraseAutopsy.created_at.asc())
        )
        return list(self.session.exec(statement).all())

    def create(
        self,
        video_id: int,
        phrase: str,
        start_time: float,
        payload: AutopsyPayload,
    ) -> PhraseAutopsy:
        row = PhraseAutopsy(
            video_id=video_id,
            phrase=phrase,
            phrase_key=normalize_phrase(phrase),
            start_time=start_time,
            register=payload["register"],
            grammar=json.dumps(payload["grammar"], ensure_ascii=False),
            natural_notes=json.dumps(payload["natural_notes"], ensure_ascii=False),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def to_response(self, row: PhraseAutopsy, youtube_id: str) -> AutopsyEntryResponse:
        return AutopsyEntryResponse(
            id=row.id,
            video_id=youtube_id,
            phrase=row.phrase,
            start_time=row.start_time,
            register=row.register,
            grammar=[AutopsyGrammarRow(**r) for r in json.loads(row.grammar)],
            natural_notes=json.loads(row.natural_notes),
            created_at=row.created_at,
        )
