from typing import List
import json
from sqlmodel import Session, select
from models.database import Video, VideoSegment


class SegmentsRepository:
    """Repository para manejar operaciones de base de datos de segmentos de video"""

    def __init__(self, session: Session):
        self.session = session

    def extract_and_save_segments(self, video: Video) -> List[VideoSegment]:
        """
        Extrae segmentos del full_transcript_data y los guarda en la base de datos.

        Args:
            video: Objeto Video con full_transcript_data

        Returns:
            Lista de VideoSegment creados
        """
        if not video.full_transcript_data:
            raise ValueError("No hay datos de transcripción detallada")

        # Parsear el JSON
        transcript_data = json.loads(video.full_transcript_data)
        segments_data = transcript_data.get("segments", [])

        # Borrar segmentos existentes si los hay
        existing_segments = self.session.exec(
            select(VideoSegment).where(VideoSegment.video_id == video.id)
        ).all()
        for seg in existing_segments:
            self.session.delete(seg)

        # Crear nuevos segmentos
        new_segments = []
        for idx, segment in enumerate(segments_data, start=1):
            video_segment = VideoSegment(
                video_id=video.id,
                segment_number=idx,
                transcript_text=segment["text"].strip(),
                start_time=segment["start"],
                end_time=segment["end"]
            )
            self.session.add(video_segment)
            new_segments.append(video_segment)

        self.session.commit()

        # Refresh segments to get their IDs
        for segment in new_segments:
            self.session.refresh(segment)

        return new_segments

    def get_by_video_id(self, video_id: int) -> List[VideoSegment]:
        """
        Obtiene todos los segmentos asociados a un video.

        Args:
            video_id: ID del video

        Returns:
            Lista de VideoSegment ordenados por segment_number
        """
        statement = select(VideoSegment).where(
            VideoSegment.video_id == video_id
        ).order_by(VideoSegment.segment_number)
        return list(self.session.exec(statement).all())

    def delete_by_video_id(self, video_id: int) -> None:
        """
        Elimina todos los segmentos de un video.

        Args:
            video_id: ID del video
        """
        segments = self.get_by_video_id(video_id)
        for segment in segments:
            self.session.delete(segment)
        self.session.commit()
