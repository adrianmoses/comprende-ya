import json
from typing import List, Optional

from sqlmodel import Session, select

from models.database import FraseExercise, Video
from models.database import Question as DBQuestion
from models.schemas import FillInBlankExercise, TimestampedQuestion, VideoResponse


class VideoRepository:
    """Repository para manejar operaciones de base de datos de videos"""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        youtube_id: str,
        youtube_url: str,
        title: str,
        duration: int,
        transcript: str,
        questions: List[TimestampedQuestion],
        full_transcript_data: Optional[dict] = None,
    ) -> Video:
        """
        Crea un nuevo video con sus preguntas.

        Args:
            youtube_id: ID del video de YouTube
            youtube_url: URL completa del video
            title: Título del video
            duration: Duración en segundos
            transcript: Transcripción completa como texto
            questions: Lista de preguntas con timestamps
            full_transcript_data: Datos detallados de transcripción (opcional)

        Returns:
            Video creado con sus preguntas
        """
        # Crear el video
        video = Video(
            youtube_id=youtube_id,
            youtube_url=youtube_url,
            title=title,
            duration=duration,
            transcript=transcript,
            full_transcript_data=json.dumps(full_transcript_data) if full_transcript_data else None,
        )

        self.session.add(video)
        self.session.flush()  # Para obtener el ID del video

        # Crear las preguntas asociadas
        for q in questions:
            db_question = DBQuestion(
                video_id=video.id,
                timestamp=q.timestamp,
                question=q.question,
                answers=json.dumps(q.answers),
                correct_answer=q.correct_answer,
                explanation=q.explanation,
            )
            self.session.add(db_question)

        self.session.commit()
        self.session.refresh(video)
        return video

    def get_by_id(self, video_id: int) -> Optional[Video]:
        """Obtiene un video por su ID"""
        return self.session.get(Video, video_id)

    def get_by_youtube_id(self, youtube_id: str) -> Optional[Video]:
        """Obtiene un video por su YouTube ID"""
        statement = select(Video).where(Video.youtube_id == youtube_id)
        return self.session.exec(statement).first()

    def list(self, skip: int = 0, limit: int = 100) -> List[Video]:
        """Lista videos con paginación"""
        statement = select(Video).offset(skip).limit(limit).order_by(Video.created_at.desc())
        return list(self.session.exec(statement).all())

    def existing_youtube_ids(self, ids: List[str]) -> List[str]:
        """youtube_ids de `ids` que existen — contrato de permalinks (027).

        Acotado por la petición (`IN`), proyecta solo la columna id: sin hidratar
        filas ni cargar relaciones, una sola ida y vuelta.
        """
        if not ids:
            return []
        statement = select(Video.youtube_id).where(Video.youtube_id.in_(ids))
        return list(self.session.exec(statement).all())

    def to_response(self, video: Video) -> VideoResponse:
        """
        Convierte un modelo de base de datos Video a VideoResponse.
        Carga las preguntas asociadas y deserializa los campos JSON.
        """
        # Cargar preguntas si no están cargadas
        if not video.questions:
            statement = select(DBQuestion).where(DBQuestion.video_id == video.id)
            video.questions = list(self.session.exec(statement).all())

        # Convertir preguntas de DB a schema
        questions = [
            TimestampedQuestion(
                timestamp=q.timestamp,
                question=q.question,
                answers=json.loads(q.answers),
                correct_answer=q.correct_answer,
                explanation=q.explanation,
            )
            for q in video.questions
        ]

        # Cargar ejercicios de fill-in-the-blank si no están cargados
        if not video.frase_exercises:
            statement = select(FraseExercise).where(FraseExercise.video_id == video.id)
            video.frase_exercises = list(self.session.exec(statement).all())

        # Convertir ejercicios de DB a schema
        fill_in_blank_exercises = (
            [
                FillInBlankExercise(
                    id=ex.id,
                    original_text=ex.original_transcript_text,
                    exercise_text=ex.exercise_text,
                    answers=json.loads(ex.answers),
                    hints=json.loads(ex.hints),
                    start_time=ex.start_time,
                    end_time=ex.end_time,
                    difficulty=ex.difficulty,
                )
                for ex in video.frase_exercises
            ]
            if video.frase_exercises
            else []
        )

        return VideoResponse(
            video_id=video.youtube_id,
            title=video.title,
            duration=video.duration,
            transcript=video.transcript,
            questions=questions,
            fill_in_blank_exercises=fill_in_blank_exercises if fill_in_blank_exercises else None,
        )
