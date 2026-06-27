"""Repositorio para `recordings` — una grabación por chunk, se sobrescribe (021).

Solo gestiona la fila; el ciclo de vida del archivo en disco vive en
`services.recording_storage` y lo orquesta la ruta."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from models.database import Recording
from models.schemas import RecordingResponse


class RecordingRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_chunk_id(self, chunk_id: int) -> Optional[Recording]:
        statement = select(Recording).where(Recording.chunk_id == chunk_id)
        return self.session.exec(statement).first()

    def upsert(
        self,
        chunk_id: int,
        file_path: str,
        content_type: str,
        size_bytes: int,
        duration_seconds: Optional[float],
    ) -> Recording:
        """Crea la grabación del chunk, o reemplaza la fila existente in situ."""
        row = self.get_by_chunk_id(chunk_id)
        if row is None:
            row = Recording(chunk_id=chunk_id)
            self.session.add(row)
        row.file_path = file_path
        row.content_type = content_type
        row.size_bytes = size_bytes
        row.duration_seconds = duration_seconds
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete(self, chunk_id: int) -> bool:
        row = self.get_by_chunk_id(chunk_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def to_response(self, row: Recording) -> RecordingResponse:
        return RecordingResponse(
            id=row.id,
            chunk_id=row.chunk_id,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            duration_seconds=row.duration_seconds,
            created_at=row.created_at,
        )
