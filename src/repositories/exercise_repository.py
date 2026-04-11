from sqlmodel import Session, select
from typing import List, Dict
import json

from models.database import FraseExercise


class ExerciseRepository:
    """Repository para manejar operaciones de base de datos de ejercicios de frases"""

    def __init__(self, session: Session):
        self.session = session

    def create_exercises(
        self,
        video_id: int,
        exercises_data: List[Dict],
    ) -> List[FraseExercise]:
        """
        Crea ejercicios de fill-in-the-blank para un video.

        Args:
            video_id: ID del video en la base de datos
            exercises_data: Lista de diccionarios con datos de ejercicios

        Returns:
            Lista de FraseExercise creados
        """
        created_exercises = []

        for exercise_dict in exercises_data:
            frase_exercise = FraseExercise(
                video_id=video_id,
                start_time=exercise_dict['start_time'],
                end_time=exercise_dict['end_time'],
                original_transcript_text=exercise_dict['original_transcript_text'],
                exercise_text=exercise_dict['exercise_text'],
                answers=json.dumps(exercise_dict['answers']),
                hints=json.dumps(exercise_dict['hints']),
                difficulty=exercise_dict['difficulty'],
            )
            self.session.add(frase_exercise)
            created_exercises.append(frase_exercise)

        self.session.commit()

        for exercise in created_exercises:
            self.session.refresh(exercise)

        return created_exercises

    def get_by_video_id(self, video_id: int) -> List[FraseExercise]:
        """
        Obtiene todos los ejercicios asociados a un video.

        Args:
            video_id: ID del video

        Returns:
            Lista de FraseExercise
        """
        statement = select(FraseExercise).where(
            FraseExercise.video_id == video_id
        ).order_by(FraseExercise.start_time)
        return list(self.session.exec(statement).all())

    def delete_by_video_id(self, video_id: int) -> None:
        """
        Elimina todos los ejercicios de un video.

        Args:
            video_id: ID del video
        """
        exercises = self.get_by_video_id(video_id)
        for exercise in exercises:
            self.session.delete(exercise)
        self.session.commit()