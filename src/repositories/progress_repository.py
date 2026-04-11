from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from models.database import AnswerProgress, Question


class ProgressRepository:
    """Repository para manejar operaciones de progreso de respuestas"""

    def __init__(self, session: Session):
        self.session = session

    def save_answer(
        self,
        video_id: int,
        question_id: int,
        user_answer: int,
        is_correct: bool
    ) -> AnswerProgress:
        """
        Guarda o actualiza el progreso de una respuesta.

        Args:
            video_id: ID del video
            question_id: ID de la pregunta
            user_answer: Índice de la respuesta seleccionada
            is_correct: Si la respuesta es correcta

        Returns:
            AnswerProgress creado o actualizado
        """
        # Buscar si ya existe progreso para esta pregunta
        statement = select(AnswerProgress).where(
            AnswerProgress.video_id == video_id,
            AnswerProgress.question_id == question_id
        )
        existing = self.session.exec(statement).first()

        if existing:
            # Actualizar existente
            existing.user_answer = user_answer
            existing.is_correct = is_correct
            existing.answered_at = datetime.utcnow()
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        else:
            # Crear nuevo
            progress = AnswerProgress(
                video_id=video_id,
                question_id=question_id,
                user_answer=user_answer,
                is_correct=is_correct
            )
            self.session.add(progress)
            self.session.commit()
            self.session.refresh(progress)
            return progress

    def get_video_progress(self, video_id: int) -> List[AnswerProgress]:
        """
        Obtiene todo el progreso para un video.

        Args:
            video_id: ID del video

        Returns:
            Lista de AnswerProgress para el video
        """
        statement = select(AnswerProgress).where(
            AnswerProgress.video_id == video_id
        )
        return list(self.session.exec(statement).all())

    def get_question_progress(self, video_id: int, question_id: int) -> Optional[AnswerProgress]:
        """
        Obtiene el progreso para una pregunta específica.

        Args:
            video_id: ID del video
            question_id: ID de la pregunta

        Returns:
            AnswerProgress si existe, None si no
        """
        statement = select(AnswerProgress).where(
            AnswerProgress.video_id == video_id,
            AnswerProgress.question_id == question_id
        )
        return self.session.exec(statement).first()

    def reset_video_progress(self, video_id: int) -> int:
        """
        Elimina todo el progreso para un video.

        Args:
            video_id: ID del video

        Returns:
            Número de registros eliminados
        """
        statement = select(AnswerProgress).where(
            AnswerProgress.video_id == video_id
        )
        progress_records = self.session.exec(statement).all()

        count = 0
        for record in progress_records:
            self.session.delete(record)
            count += 1

        self.session.commit()
        return count

    def get_progress_summary(self, video_id: int) -> dict:
        """
        Obtiene un resumen del progreso para un video.

        Args:
            video_id: ID del video

        Returns:
            Diccionario con estadísticas de progreso
        """
        progress_records = self.get_video_progress(video_id)

        total_answered = len(progress_records)
        total_correct = sum(1 for p in progress_records if p.is_correct)

        return {
            "answered": total_answered,
            "correct": total_correct,
            "incorrect": total_answered - total_correct
        }
