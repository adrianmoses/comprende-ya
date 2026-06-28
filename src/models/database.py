from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship, SQLModel


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
    phrase_autopsies: List["PhraseAutopsy"] = Relationship(back_populates="video")
    chunks: List["Chunk"] = Relationship(back_populates="video")


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
    end_time: float  # en segundos
    tokens: Optional[str] = None  # JSON string de la lista de tokens del segmento (018)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con Video
    video: Optional["Video"] = Relationship(back_populates="segments")


class AnswerProgress(SQLModel, table=True):
    """Modelo para trackear progreso de respuestas"""

    __tablename__ = "answer_progress"
    __table_args__ = (
        UniqueConstraint("video_id", "question_id", name="unique_video_question_progress"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # FK ondelete declarado en el modelo para que coincida con el esquema (029).
    video_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    question_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    user_answer: int  # Índice de la respuesta seleccionada (0-3)
    is_correct: bool
    answered_at: datetime = Field(default_factory=datetime.utcnow)


class FraseExercise(SQLModel, table=True):
    __tablename__ = "frase_exercise"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    start_time: float
    end_time: float
    original_transcript_text: str
    exercise_text: str  # Con los blanks
    answers: str  # JSON string
    hints: str  # JSON string
    difficulty: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con Video
    video: Optional[Video] = Relationship(back_populates="frase_exercises")


class PhraseAutopsy(SQLModel, table=True):
    """Autopsia (en español) de una frase concreta de un vídeo, generada por Claude."""

    __tablename__ = "phrase_autopsy"
    __table_args__ = (
        UniqueConstraint("video_id", "phrase_key", name="uq_phrase_autopsy_video_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    phrase: str  # casing original para mostrar
    phrase_key: str = Field(index=True)  # normalizado para búsqueda en caché
    start_time: float
    register: str
    grammar: str  # JSON string de [{tag, text}]
    natural_notes: str  # JSON string de [string]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    video: Optional[Video] = Relationship(back_populates="phrase_autopsies")


class Chunk(SQLModel, table=True):
    """Frase guardada en la biblioteca de Mis frases, con consignas de práctica."""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("video_id", "phrase_key", name="uq_chunks_video_phrase"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="videos.id", index=True)
    phrase: str  # casing original para mostrar
    phrase_key: str = Field(index=True)  # normalizado para búsqueda en caché
    start_time: float
    prompts: str  # JSON string de [string] — 2-4 consignas de uso en español
    created_at: datetime = Field(default_factory=datetime.utcnow)

    video: Optional[Video] = Relationship(back_populates="chunks")
    recording: Optional["Recording"] = Relationship(
        back_populates="chunk",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )


class Recording(SQLModel, table=True):
    """Grabación de voz del usuario para un chunk — una por chunk, se sobrescribe (021).

    Los bytes de audio viven en disco bajo `settings.RECORDINGS_DIR`; aquí solo se
    guarda la ruta + metadatos. Sin evaluación/ASR: es para que el usuario se
    reescuche."""

    __tablename__ = "recordings"

    id: Optional[int] = Field(default=None, primary_key=True)
    chunk_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            unique=True,
        )
    )
    file_path: str  # ruta relativa bajo RECORDINGS_DIR, nombre generado en servidor
    content_type: str  # p.ej. "audio/webm;codecs=opus" — se devuelve al reproducir
    size_bytes: int
    duration_seconds: Optional[float] = None  # mejor esfuerzo, informado por el cliente
    created_at: datetime = Field(default_factory=datetime.utcnow)

    chunk: Optional[Chunk] = Relationship(back_populates="recording")


class ProcessingJob(SQLModel, table=True):
    """Estado persistido de un flow de procesamiento de video."""

    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED')",
            name="ck_processing_jobs_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    flow_run_id: str = Field(index=True, unique=True, max_length=36)
    youtube_url: str
    youtube_video_id: str = Field(index=True, max_length=32)
    status: str = Field(default="PENDING", max_length=16, index=True)
    error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    video_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Profile(SQLModel, table=True):
    """Perfil singleton del único usuario (sin auth). Una sola fila (id=1),
    creada de forma perezosa por el repositorio (022)."""

    __tablename__ = "profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Ana")
    level: str = Field(default="B2")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StudySession(SQLModel, table=True):
    """Registro append-only de tiempo de escucha. Cada fila son `seconds` de
    reproducción reportados por el frontend; los minutos de la semana se suman
    sobre `created_at` (022)."""

    __tablename__ = "study_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    seconds: int
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
