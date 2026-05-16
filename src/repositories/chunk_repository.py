"""Repositorio para `chunks` — caché por (video_id, phrase_key) con consignas."""

from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from models.database import Chunk
from models.schemas import ChunkResponse
from repositories.autopsy_repository import normalize_phrase


class ChunkRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_phrase(self, video_id: int, phrase_key: str) -> Optional[Chunk]:
        statement = select(Chunk).where(
            Chunk.video_id == video_id,
            Chunk.phrase_key == phrase_key,
        )
        return self.session.exec(statement).first()

    def list_all(self) -> List[Chunk]:
        statement = (
            select(Chunk).options(selectinload(Chunk.video)).order_by(Chunk.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def create(
        self,
        video_id: int,
        phrase: str,
        start_time: float,
        prompts: List[str],
    ) -> Chunk:
        row = Chunk(
            video_id=video_id,
            phrase=phrase,
            phrase_key=normalize_phrase(phrase),
            start_time=start_time,
            prompts=json.dumps(prompts, ensure_ascii=False),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete(self, chunk_id: int) -> bool:
        row = self.session.get(Chunk, chunk_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def to_response(self, row: Chunk) -> ChunkResponse:
        return ChunkResponse(
            id=row.id,
            video_id=row.video.youtube_id,
            source_title=row.video.title,
            phrase=row.phrase,
            start_time=row.start_time,
            prompts=json.loads(row.prompts),
            created_at=row.created_at,
        )
