from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from datetime import datetime
from typing import Optional, List


class Video(SQLModel, table=True):
    """Modelo de base de datos para videos procesados"""
    __tablename__ = "videos"

    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_id: str = Field(index=True, unique=True)
    youtube_url: str
    title: str
    duration: int  # en segundos
    transcript: str
    full_transcript_data: Optional[str] = None  # JSON string de DetailedTranscript
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con preguntas
    questions: List["Question"] = Relationship(back_populates="video")
    segments: List["VideoSegment"] = Relationship(back_populates="video")
    frase_exercises: List["FraseExercise"] = Relationship(back_populates="video")



class Question(SQLModel, table=True):
    """Modelo de base de datos para preguntas de comprensión"""
    __tablename__ = "questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    timestamp: float  # Segundos desde el inicio del video
    question: str
    answers: str  # JSON string de la lista de respuestas
    correct_answer: int  # Índice de la respuesta correcta (0-3)
    explanation: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con video
    video: Optional[Video] = Relationship(back_populates="questions")


class VideoSegment(SQLModel, table=True):
    """Modelo para segmentos de transcripción con timestamps"""
    __tablename__ = "video_segments"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    segment_number: int
    transcript_text: str
    start_time: float  # en segundos
    end_time: float    # en segundos
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con Video
    video: Optional["Video"] = Relationship(back_populates="segments")


class AnswerProgress(SQLModel, table=True):
    """Modelo para trackear progreso de respuestas"""
    __tablename__ = "answer_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    question_id: int = Field(foreign_key="questions.id", index=True)
    user_answer: int  # Índice de la respuesta seleccionada (0-3)
    is_correct: bool
    answered_at: datetime = Field(default_factory=datetime.utcnow)


class FraseExercise(SQLModel, table=True):
    __tablename__ = "frase_exercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    start_time: float
    end_time: float
    original_transcript_text: str
    exercise_text: str # Con los blanks
    answers: str  # JSON string
    hints: str  # JSON string
    difficulty: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con Video
    video: Optional[Video] = Relationship(back_populates="frase_exercises")